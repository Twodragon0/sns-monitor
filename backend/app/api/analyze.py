"""
URL analysis API routes.
POST /api/analyze/url - Analyze content from any supported platform URL
GET  /api/platforms   - List supported platforms
"""

import logging
from flask import request, jsonify

from . import analyze_bp
from .. import limiter
from ..config import Config

logger = logging.getLogger(__name__)

# Lazy-loaded platform analyzer
_platform_analyzer = None


def _get_analyzer():
    global _platform_analyzer
    if _platform_analyzer is None:
        from ..services.platform_analyzer import PlatformAnalyzer

        _platform_analyzer = PlatformAnalyzer(data_dir=Config.LOCAL_DATA_DIR)
    return _platform_analyzer


# Max URL length to prevent abuse and oversized payloads
MAX_ANALYZE_URL_LENGTH = 2048


@analyze_bp.route("/api/analyze/url", methods=["POST"])
@limiter.limit("30 per minute")
def analyze_url():
    """Analyze content from any supported platform URL."""
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify(
            {"error": "URL is required", "usage": {"url": "https://..."}}
        ), 400

    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400
    if len(url) > MAX_ANALYZE_URL_LENGTH:
        return jsonify(
            {"error": f"URL too long (max {MAX_ANALYZE_URL_LENGTH} characters)"}
        ), 400
    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "Invalid URL format"}), 400

    try:
        result = _get_analyzer().analyze(url)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("Analysis error for %s: %s", url, e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@analyze_bp.route("/api/analyze/summarize", methods=["POST"])
@limiter.limit("10 per minute")
def summarize_analysis():
    """Summarize analysis results using MiroFish AI service."""
    data = request.get_json(silent=True)
    if not data or "result" not in data:
        return jsonify({"error": "Analysis result is required"}), 400

    result = data["result"]

    # Build document text from analysis result
    lines = []
    platform = result.get("platform", "unknown")
    title = result.get(
        "title",
        result.get(
            "gallery_id", result.get("subreddit", result.get("username", "Unknown"))
        ),
    )
    lines.append(f"# {platform.upper()} Analysis: {title}")
    lines.append(f"Analyzed at: {result.get('analyzed_at', 'N/A')}")
    lines.append("")

    if result.get("description"):
        lines.append(f"## Description")
        lines.append(result["description"])
        lines.append("")

    # Stats
    stat_keys = [
        "view_count",
        "like_count",
        "comment_count",
        "subscriber_count",
        "follower_count",
        "tweet_count",
        "total_posts",
        "score",
    ]
    stats = {k: result[k] for k in stat_keys if result.get(k) is not None}
    if stats:
        lines.append("## Stats")
        for k, v in stats.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    # Naver Cafe fetch status (수집 제한 시 요약 문서에 포함)
    fetch_status = result.get("fetch_status")
    fetch_reason = result.get("fetch_reason", "")
    if fetch_status and fetch_status != "ok":
        lines.append("## 수집 상태")
        lines.append(f"- fetch_status: {fetch_status}")
        if fetch_reason:
            lines.append(f"- fetch_reason: {fetch_reason}")
        lines.append("")

    # Single post body (네이버 카페 단일글 본문 등)
    if result.get("content"):
        lines.append("## 본문")
        lines.append((result["content"] or "")[:3000])
        lines.append("")

    # Posts/Comments content
    items = result.get("comments", result.get("posts", result.get("recent_videos", [])))
    if items:
        item_type = "Comments" if "comments" in result else "Posts"
        lines.append(f"## {item_type} ({len(items)} items)")
        for i, item in enumerate(items[:30]):
            text = item.get("text", item.get("title", item.get("selftext", "")))
            if text:
                lines.append(f"{i + 1}. {text[:200]}")
        lines.append("")

    # Sentiment analysis
    analysis = result.get("analysis")
    if analysis:
        lines.append("## Sentiment Analysis")
        lines.append(f"- Overall: {analysis.get('overall', 'N/A')}")
        sentiment = analysis.get("sentiment", {})
        lines.append(
            f"- Positive: {sentiment.get('positive', 0)}, Neutral: {sentiment.get('neutral', 0)}, Negative: {sentiment.get('negative', 0)}"
        )
        top_kw = analysis.get("top_keywords", [])[:10]
        if top_kw:
            kw_str = ", ".join(f"{kw['word']}({kw['count']})" for kw in top_kw)
            lines.append(f"- Top keywords: {kw_str}")

    document = "\n".join(lines)

    # Send to MiroFish for summarization
    mirofish_endpoint = Config.MIROFISH_ENDPOINT
    try:
        import requests as req

        resp = req.post(
            f"{mirofish_endpoint}/api/report/generate",
            json={
                "documents": [{"content": document, "title": title}],
                "prompt": f"Analyze and summarize this {platform} content in Korean. "
                "Include: 1) Overall summary 2) Key topics/themes "
                "3) Sentiment overview 4) Notable findings",
                "format": "markdown",
            },
            timeout=60,
            verify=Config.MIROFISH_SSL_VERIFY,
        )
        if resp.ok:
            report = resp.json()
            return jsonify(
                {
                    "summary": report.get(
                        "report", report.get("content", report.get("result", ""))
                    ),
                    "source": "mirofish",
                }
            )
        else:
            logger.warning(f"MiroFish returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"MiroFish summarization failed: {e}")

    # Fallback: generate a readable plain-text summary in Korean (no markdown)
    def _fmt_num(v):
        if v is None:
            return "0"
        try:
            n = int(v)
            return f"{n:,}" if n >= 0 else str(n)
        except (TypeError, ValueError):
            return str(v)

    _stat_labels = {
        "view_count": "조회수",
        "like_count": "좋아요",
        "comment_count": "댓글 수",
        "subscriber_count": "구독자",
        "follower_count": "팔로워",
        "tweet_count": "트윗 수",
        "total_posts": "총 게시글",
        "score": "점수",
    }
    _platform_names = {
        "youtube": "YouTube",
        "dcinside": "DCInside",
        "naver_cafe": "네이버 카페",
        "reddit": "Reddit",
        "telegram": "Telegram",
        "kakao": "Kakao",
        "twitter": "X (Twitter)",
        "instagram": "Instagram",
        "facebook": "Facebook",
        "threads": "Threads",
    }
    platform_display = _platform_names.get(platform, platform.upper())

    summary_lines = [f"{title} 분석 요약"]
    summary_lines.append("")
    summary_lines.append(f"플랫폼: {platform_display}")

    if stats:
        stat_parts = []
        for k, v in stats.items():
            label = _stat_labels.get(k, k)
            stat_parts.append(f"{label} {_fmt_num(v)}")
        summary_lines.append("주요 지표: " + ", ".join(stat_parts))

    if analysis:
        overall = analysis.get("overall", "neutral")
        overall_kr = {
            "positive": "긍정적",
            "neutral": "중립적",
            "negative": "부정적",
        }.get(overall, overall)
        summary_lines.append(f"전체 감성: {overall_kr}")
        total = analysis.get("total", 0)
        sentiment = analysis.get("sentiment", {}) or {}
        if total and total > 0:
            pos = sentiment.get("positive", 0) or 0
            neg = sentiment.get("negative", 0) or 0
            summary_lines.append(
                f"감성 분포: 총 {_fmt_num(total)}건 중 긍정 {_fmt_num(pos)}건, 부정 {_fmt_num(neg)}건"
            )
        top_kw = (analysis.get("top_keywords") or [])[:8]
        if top_kw:
            kw_str = ", ".join(kw.get("word", "") for kw in top_kw if kw.get("word"))
            if kw_str:
                summary_lines.append(f"주요 키워드: {kw_str}")

    if items:
        summary_lines.append(f"수집된 콘텐츠: {_fmt_num(len(items))}건")

    if fetch_status and fetch_status != "ok":
        summary_lines.append("")
        summary_lines.append("⚠ 수집 상태: 콘텐츠가 정상 수집되지 않았습니다.")
        if platform == "naver_cafe":
            summary_lines.append(
                "네이버 카페는 로그인·제한 정책으로 수집이 막힐 수 있습니다. "
                ".env에 NAVER_CAFE_COOKIE(로그인 쿠키)를 설정하면 수집 가능성이 높아집니다. "
                "필요 시 NAVER_CAFE_PROXY_URL도 설정하세요."
            )
        if fetch_reason:
            summary_lines.append(f"원인: {fetch_reason}")
    elif not items and result.get("content"):
        summary_lines.append("수집된 본문이 요약에 반영되었습니다.")

    return jsonify(
        {
            "summary": "\n".join(summary_lines),
            "source": "local",
        }
    )


@analyze_bp.route("/api/platforms", methods=["GET"])
def list_platforms():
    """List supported platforms with example URLs."""
    analyzer = _get_analyzer()
    return jsonify({
        "platforms": analyzer.list_platforms(),
        "api_usage": analyzer.get_api_usage(),
    })
