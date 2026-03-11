"""
URL analysis API routes.
POST /api/analyze/url - Analyze content from any supported platform URL
GET  /api/platforms   - List supported platforms
"""

import logging
from flask import request, jsonify

from . import analyze_bp
from ..config import Config

logger = logging.getLogger(__name__)

# Lazy-loaded platform analyzer
_platform_analyzer = None


def _get_analyzer():
    global _platform_analyzer
    if _platform_analyzer is None:
        from ..services.platform_analyzer import PlatformAnalyzer
        _platform_analyzer = PlatformAnalyzer(
            data_dir=Config.LOCAL_DATA_DIR
        )
    return _platform_analyzer


@analyze_bp.route('/api/analyze/url', methods=['POST'])
def analyze_url():
    """Analyze content from any supported platform URL."""
    data = request.get_json(silent=True)
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required', 'usage': {'url': 'https://...'}}), 400

    url = data['url'].strip()
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    try:
        result = _get_analyzer().analyze(url)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error("Analysis error for %s: %s", url, e, exc_info=True)
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@analyze_bp.route('/api/analyze/summarize', methods=['POST'])
def summarize_analysis():
    """Summarize analysis results using MiroFish AI service."""
    data = request.get_json(silent=True)
    if not data or 'result' not in data:
        return jsonify({'error': 'Analysis result is required'}), 400

    result = data['result']

    # Build document text from analysis result
    lines = []
    platform = result.get('platform', 'unknown')
    title = result.get('title', result.get('gallery_id', result.get('subreddit', result.get('username', 'Unknown'))))
    lines.append(f"# {platform.upper()} Analysis: {title}")
    lines.append(f"Analyzed at: {result.get('analyzed_at', 'N/A')}")
    lines.append("")

    if result.get('description'):
        lines.append(f"## Description")
        lines.append(result['description'])
        lines.append("")

    # Stats
    stat_keys = ['view_count', 'like_count', 'comment_count', 'subscriber_count',
                 'follower_count', 'tweet_count', 'total_posts', 'score']
    stats = {k: result[k] for k in stat_keys if result.get(k) is not None}
    if stats:
        lines.append("## Stats")
        for k, v in stats.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    # Posts/Comments content
    items = result.get('comments', result.get('posts', result.get('recent_videos', [])))
    if items:
        item_type = 'Comments' if 'comments' in result else 'Posts'
        lines.append(f"## {item_type} ({len(items)} items)")
        for i, item in enumerate(items[:30]):
            text = item.get('text', item.get('title', item.get('selftext', '')))
            if text:
                lines.append(f"{i+1}. {text[:200]}")
        lines.append("")

    # Sentiment analysis
    analysis = result.get('analysis')
    if analysis:
        lines.append("## Sentiment Analysis")
        lines.append(f"- Overall: {analysis.get('overall', 'N/A')}")
        sentiment = analysis.get('sentiment', {})
        lines.append(f"- Positive: {sentiment.get('positive', 0)}, Neutral: {sentiment.get('neutral', 0)}, Negative: {sentiment.get('negative', 0)}")
        top_kw = analysis.get('top_keywords', [])[:10]
        if top_kw:
            kw_str = ', '.join(f"{kw['word']}({kw['count']})" for kw in top_kw)
            lines.append(f"- Top keywords: {kw_str}")

    document = '\n'.join(lines)

    # Send to MiroFish for summarization
    mirofish_endpoint = Config.MIROFISH_ENDPOINT
    try:
        import requests as req
        resp = req.post(
            f'{mirofish_endpoint}/api/report/generate',
            json={
                'documents': [{'content': document, 'title': title}],
                'prompt': f'Analyze and summarize this {platform} content in Korean. '
                          'Include: 1) Overall summary 2) Key topics/themes '
                          '3) Sentiment overview 4) Notable findings',
                'format': 'markdown',
            },
            timeout=60,
            verify=False,
        )
        if resp.ok:
            report = resp.json()
            return jsonify({
                'summary': report.get('report', report.get('content', report.get('result', ''))),
                'source': 'mirofish',
            })
        else:
            logger.warning(f'MiroFish returned {resp.status_code}: {resp.text[:200]}')
    except Exception as e:
        logger.warning(f'MiroFish summarization failed: {e}')

    # Fallback: generate a basic summary locally
    summary_lines = [f"## {title} 분석 요약\n"]
    summary_lines.append(f"**플랫폼:** {platform.upper()}")
    if stats:
        summary_lines.append(f"**주요 지표:** {', '.join(f'{k}={v}' for k, v in stats.items())}")
    if analysis:
        overall = analysis.get('overall', 'neutral')
        overall_kr = {'positive': '긍정적', 'neutral': '중립적', 'negative': '부정적'}.get(overall, overall)
        summary_lines.append(f"**전체 감성:** {overall_kr}")
        total = analysis.get('total', 0)
        if total > 0:
            pos = sentiment.get('positive', 0)
            neg = sentiment.get('negative', 0)
            summary_lines.append(f"**감성 분포:** 총 {total}건 중 긍정 {pos}건, 부정 {neg}건")
        if top_kw:
            summary_lines.append(f"**주요 키워드:** {', '.join(kw['word'] for kw in top_kw[:5])}")
    if items:
        summary_lines.append(f"**콘텐츠 수:** {len(items)}건 수집")

    return jsonify({
        'summary': '\n'.join(summary_lines),
        'source': 'local',
    })


@analyze_bp.route('/api/platforms', methods=['GET'])
def list_platforms():
    """List supported platforms with example URLs."""
    return jsonify({
        'platforms': _get_analyzer().list_platforms()
    })
