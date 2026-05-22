"""
SNS local analysis, sentiment, LLM AI routes.
MiroFish proxy routes are in analysis_mirofish.py.
"""

import json
import logging
import os  # noqa: F401 — used by analysis_mirofish via this module's namespace
import re
from datetime import datetime
from pathlib import Path

import requests  # noqa: F401 — used by analysis_mirofish via this module's namespace
from flask import request, jsonify

from . import analysis_bp, csrf_protect
from .auth import require_analysis_auth
from .. import limiter
from ..config import Config

# Alphanumeric + hyphens + underscores only for path IDs
_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_@-]{1,128}$')

# Chat history validation constants
MAX_CHAT_HISTORY = 20
ALLOWED_CHAT_ROLES = {"user", "assistant"}

logger = logging.getLogger(__name__)

# Re-export MiroFish helpers for backward compatibility (tests import from here)
from .analysis_mirofish import _mirofish_headers, _proxy_json, MIROFISH_URL  # noqa: F401


def _validate_chat_history(data):
    """Validate and sanitize chat_history from request data.

    Returns a validated list of message dicts, or None if the raw value is not
    a list. Callers translate None into a constant error response so that user
    input never flows into the HTTP response body (avoids CodeQL py/reflective-xss).
    """
    raw_history = data.get('chat_history', [])
    if not isinstance(raw_history, list):
        return None
    chat_history = []
    for msg in raw_history[:MAX_CHAT_HISTORY]:
        if not isinstance(msg, dict):
            continue
        role = msg.get('role', '')
        content = msg.get('content', '')
        if role not in ALLOWED_CHAT_ROLES or not isinstance(content, str):
            continue
        chat_history.append({'role': role, 'content': content[:5000]})
    return chat_history


def _get_local_data_dir():
    return Path(Config.LOCAL_DATA_DIR)


def _extract_sentiment_items(data, include_content=True, max_posts=200, max_comments_per_post=5):
    """Extract text items from crawled JSON data for sentiment analysis.

    Args:
        data: parsed JSON from a crawl file
        include_content: if True, append post content snippet to text
        max_posts: max number of posts to process
        max_comments_per_post: max comments per post
    Returns:
        list of {'text': str} dicts
    """
    items = []
    for post in data.get('posts', data.get('data', []))[:max_posts]:
        p = post.get('post', post)
        text = p.get('text', '') or p.get('title', '')
        if text:
            if include_content:
                content = post.get('content', p.get('content', ''))
                text = f"{text} {(content or '')[:200]}".strip()
            items.append({'text': text})
        for c in post.get('comments', [])[:max_comments_per_post]:
            ctext = c.get('text', c.get('content', ''))
            if ctext:
                items.append({'text': ctext})
    return items


def _build_document_from_url_result(url_result, compact=False):
    """Build a Markdown document from a URL analyzer result dict.

    Args:
        url_result: dict from URL analyzer
        compact: if True, produce a shorter version (for chat context)
    """
    platform = url_result.get('platform', 'unknown')
    title = url_result.get('title', url_result.get('username', 'Unknown'))
    lines = [f"# {platform.upper()} Analysis: {title}"]

    if url_result.get('description'):
        limit = 1000 if compact else len(url_result['description'])
        lines.append(f"\n## Description\n{url_result['description'][:limit]}")

    if not compact and url_result.get('content'):
        lines.append(f"\n## Content\n{str(url_result['content'])[:3000]}")

    # Stats (full mode only)
    if not compact:
        stat_keys = ['view_count', 'like_count', 'comment_count', 'subscriber_count',
                     'follower_count', 'tweet_count', 'total_posts', 'score']
        stats = {k: url_result[k] for k in stat_keys if url_result.get(k) is not None}
        if stats:
            lines.append("\n## Stats")
            for k, v in stats.items():
                lines.append(f"- {k}: {v}")

    # Posts/Comments
    items = (url_result.get('comments') or url_result.get('replies')
             or url_result.get('posts') or url_result.get('recent_videos') or [])
    max_items = 30 if compact else 50
    if items:
        label = 'Comments' if url_result.get('comments') else 'Posts'
        lines.append(f"\n## {label} ({len(items)} items)")
        text_limit = 150 if compact else 200
        for i, item in enumerate(items[:max_items]):
            text = item.get('text', item.get('title', ''))
            author = item.get('author', '')
            if text:
                if compact:
                    lines.append(f"- {str(text)[:text_limit]}")
                else:
                    lines.append(f"{i+1}. [{author}] {str(text)[:text_limit]}")

    # Existing sentiment (full mode only)
    if not compact:
        analysis = url_result.get('analysis')
        if analysis:
            lines.append("\n## Existing Sentiment Analysis")
            lines.append(f"- Overall: {analysis.get('overall', 'N/A')}")
            s = analysis.get('sentiment', {})
            lines.append(f"- Positive: {s.get('positive', 0)}, Neutral: {s.get('neutral', 0)}, Negative: {s.get('negative', 0)}")

    return '\n'.join(lines)


def _build_documents_from_sources(sources_list):
    """Build Markdown documents from a list of source dicts.

    Returns the document list on success, or None when any source id fails the
    safe-id regex. Callers translate None into a constant error response so that
    user input never flows into the HTTP response body (CodeQL py/reflective-xss).
    """
    documents = []
    for src in sources_list:
        src_type = src.get('type', '')
        src_id = src.get('id', '')
        if not _SAFE_ID_RE.match(src_id):
            return None

        if src_type == 'youtube':
            doc = _transform_youtube_to_document(src_id)
        elif src_type == 'dcinside':
            doc = _transform_dcinside_to_document(src_id)
        else:
            continue

        if doc:
            documents.append(doc)

    return documents


def _transform_youtube_to_document(channel_handle):
    """Transform YouTube crawler data into a Markdown document for AI analysis."""
    data_dir = _get_local_data_dir() / 'youtube' / 'channels'
    lines = []

    for json_file in sorted(data_dir.glob(f'{channel_handle}*.json'), reverse=True)[:5]:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            channel_name = data.get('channel_name', channel_handle)
            lines.append(f"# YouTube Analysis: {channel_name} ({json_file.stem})")
            lines.append("")

            for video_entry in data.get('recent_videos', data.get('data', []))[:10]:
                video = video_entry.get('video', video_entry)
                title = video.get('title', 'Unknown')
                views = video.get('view_count', video.get('views', 0))
                likes = video.get('like_count', video.get('likes', 0))
                comments_count = video.get('comment_count', video.get('comments', 0))

                lines.append(f"## Video: {title}")
                lines.append(f"- Views: {views:,} / Likes: {likes:,} / Comments: {comments_count}")
                lines.append("")

                comments = video_entry.get('comments', [])
                if comments:
                    lines.append("### Comments")
                    for c in comments[:20]:
                        text = c.get('text', '')
                        c_likes = c.get('likes', c.get('like_count', 0))
                        sentiment = c.get('sentiment', '')
                        lines.append(f"- \"{text}\" (likes: {c_likes}, sentiment: {sentiment})")
                    lines.append("")
        except Exception as e:
            logger.warning("Failed to read %s: %s", json_file, e)

    return '\n'.join(lines) if lines else None


def _transform_dcinside_to_document(gallery_id):
    """Transform DCInside crawler data into a Markdown document for AI analysis."""
    data_dir = _get_local_data_dir() / 'dcinside' / gallery_id
    lines = []

    if not data_dir.exists():
        return None

    for json_file in sorted(data_dir.glob('*.json'), reverse=True)[:5]:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            lines.append(f"# DCInside Gallery: {gallery_id} ({json_file.stem})")
            lines.append("")

            posts = data.get('posts', data.get('data', []))
            for post_entry in posts[:20]:
                post = post_entry.get('post', post_entry)
                title = post.get('title', 'No title')
                author = post.get('author', 'anonymous')
                views = post.get('views', post.get('view_count', 0))

                lines.append(f"## Post: {title}")
                lines.append(f"- Author: {author} / Views: {views}")

                content = post_entry.get('content', post.get('content', ''))
                if content:
                    lines.append(f"- Content: {content[:500]}")

                comments = post_entry.get('comments', [])
                if comments:
                    for c in comments[:10]:
                        c_text = c.get('text', c.get('content', ''))
                        lines.append(f"  - Comment: \"{c_text}\"")
                lines.append("")
        except Exception as e:
            logger.warning("Failed to read %s: %s", json_file, e)

    return '\n'.join(lines) if lines else None


def _source_display_name_youtube(json_path):
    """Extract channel display name from YouTube crawler JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('channel_title') or data.get('channel_name') or json_path.stem
    except Exception:
        return json_path.stem


@analysis_bp.route('/api/analysis/sources', methods=['GET'])
@limiter.limit("30 per minute")
def list_available_sources():
    """List available SNS data sources that can be analyzed (for AI analysis/summary)."""
    data_dir = Path(Config.LOCAL_DATA_DIR)
    sources = []

    # YouTube channels (local-data/youtube/channels/*.json)
    yt_dir = data_dir / 'youtube' / 'channels'
    if yt_dir.exists():
        for f in yt_dir.glob('*.json'):
            sources.append({
                'type': 'youtube',
                'id': f.stem,
                'name': _source_display_name_youtube(f),
                'file': str(f.name),
                'size': f.stat().st_size,
            })

    # DCInside galleries (local-data/dcinside/<gallery_id>/*.json)
    dc_dir = data_dir / 'dcinside'
    if dc_dir.exists():
        for gallery_dir in dc_dir.iterdir():
            if gallery_dir.is_dir():
                json_files = list(gallery_dir.glob('*.json'))
                if json_files:
                    # Prefer gallery name from latest JSON if available
                    name = gallery_dir.name
                    try:
                        latest = max(json_files, key=lambda p: p.stat().st_mtime)
                        with open(latest, 'r', encoding='utf-8') as fp:
                            data = json.load(fp)
                        name = data.get('gallery_name') or name
                    except Exception as e:
                        logger.debug("Could not read gallery name for %s: %s", gallery_dir.name, e)
                    sources.append({
                        'type': 'dcinside',
                        'id': gallery_dir.name,
                        'name': name,
                        'files': len(json_files),
                        'latest': max(f.name for f in json_files),
                    })

    return jsonify({'sources': sources})


def _read_source_items(src_type, src_id):
    """Read crawled items from local JSON files for local sentiment analysis."""
    data_dir = _get_local_data_dir()
    items = []
    stats = {}

    if src_type == 'youtube':
        yt_dir = data_dir / 'youtube' / 'channels'
        for json_file in sorted(yt_dir.glob(f'{src_id}*.json'), reverse=True)[:3]:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                stats['channel_name'] = data.get('channel_name', src_id)
                for video in data.get('recent_videos', data.get('data', []))[:10]:
                    v = video.get('video', video)
                    stats.setdefault('video_count', 0)
                    stats['video_count'] += 1
                    for c in video.get('comments', [])[:30]:
                        items.append({'text': c.get('text', ''), 'author': c.get('author', '')})
            except Exception as e:
                logger.debug("Failed to load YouTube data for %s: %s", src_id, e)

    elif src_type == 'dcinside':
        dc_dir = data_dir / 'dcinside' / src_id
        if dc_dir.exists():
            for json_file in sorted(dc_dir.glob('*.json'), reverse=True)[:3]:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    stats['gallery_name'] = data.get('gallery_name', src_id)
                    for post in data.get('posts', data.get('data', []))[:200]:
                        p = post.get('post', post)
                        text = p.get('text', '') or p.get('title', '')
                        content = post.get('content', p.get('content', ''))
                        full_text = f"{text} {(content or '')[:300]}".strip()
                        if full_text:
                            items.append({'text': full_text, 'author': p.get('author', '')})
                        for c in post.get('comments', [])[:10]:
                            items.append({'text': c.get('text', c.get('content', '')), 'author': c.get('author', '')})
                except Exception as e:
                    logger.debug("Failed to load DCInside data from %s: %s", json_file, e)

    return items, stats


@analysis_bp.route('/api/analysis/local-summary', methods=['POST'])
@limiter.limit("10 per minute")
@csrf_protect
def local_summary():
    """
    Local analysis: reads crawled data and runs keyword-based sentiment analysis.
    Works offline — no external AI service required.
    """
    from ..services.sentiment_analyzer import SentimentAnalyzer

    data = request.get_json() or {}
    sources_list = data.get('sources', [])
    if not sources_list:
        return jsonify({'error': 'No data sources specified'}), 400

    analyzer = SentimentAnalyzer()
    all_items = []
    source_summaries = []

    for src in sources_list:
        src_type = src.get('type', '')
        src_id = src.get('id', '')
        if not _SAFE_ID_RE.match(src_id):
            return jsonify({'error': 'Invalid source id'}), 400

        items, stats = _read_source_items(src_type, src_id)
        if not items:
            continue

        sentiment = analyzer.analyze(items)
        all_items.extend(items)
        source_summaries.append({
            'type': src_type,
            'id': src_id,
            'name': stats.get('channel_name') or stats.get('gallery_name') or src_id,
            'item_count': len(items),
            'sentiment': sentiment,
        })

    if not source_summaries:
        return jsonify({'error': 'No data found for specified sources'}), 404

    # Overall combined sentiment
    overall_sentiment = analyzer.analyze(all_items)

    return jsonify({
        'success': True,
        'mode': 'local',
        'sources': source_summaries,
        'overall': overall_sentiment,
        'total_items': len(all_items),
    })


@analysis_bp.route('/api/analysis/trend', methods=['GET'])
@limiter.limit("30 per minute")
def sentiment_trend():
    """Return sentiment over time for a gallery (one data point per crawl file).

    Query params: type=dcinside&id=skoshism
    """
    from ..services.sentiment_analyzer import SentimentAnalyzer

    src_type = request.args.get('type', 'dcinside')
    src_id = request.args.get('id', '')
    if not src_id or not _SAFE_ID_RE.match(src_id):
        return jsonify({'error': 'Invalid source id'}), 400

    data_dir = _get_local_data_dir()
    analyzer = SentimentAnalyzer()
    trend = []

    if src_type == 'dcinside':
        dc_dir = data_dir / 'dcinside' / src_id
        if not dc_dir.exists():
            return jsonify({'error': 'Source not found'}), 404

        for json_file in sorted(dc_dir.glob('*.json'))[-20:]:  # last 20 files
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Parse timestamp from filename (2026-03-18-12-30-05.json)
                fname = json_file.stem
                parts = fname.split('-')
                if len(parts) >= 5:
                    ts = f"{parts[0]}-{parts[1]}-{parts[2]}T{parts[3]}:{parts[4]}:00"
                else:
                    ts = data.get('collected_at', fname)

                items = _extract_sentiment_items(data)

                if items:
                    sentiment = analyzer.analyze(items)
                    s = sentiment.get('sentiment', {})
                    trend.append({
                        'timestamp': ts,
                        'total': sentiment.get('total', 0),
                        'positive': s.get('positive', 0),
                        'neutral': s.get('neutral', 0),
                        'negative': s.get('negative', 0),
                        'keywords': [k['word'] for k in sentiment.get('top_keywords', [])[:5]],
                    })
            except Exception as e:
                logger.warning("Failed to process trend file %s: %s", json_file, e)

    return jsonify({
        'source_id': src_id,
        'source_type': src_type,
        'trend': trend,
    })


@analysis_bp.route('/api/analysis/compare', methods=['GET'])
@limiter.limit("10 per minute")
def gallery_compare():
    """Compare sentiment across all DCInside galleries.

    Returns sorted list of galleries with their latest sentiment stats.
    """
    from ..services.sentiment_analyzer import SentimentAnalyzer

    data_dir = _get_local_data_dir()
    dc_dir = data_dir / 'dcinside'
    if not dc_dir.exists():
        return jsonify({'galleries': []})

    analyzer = SentimentAnalyzer()
    galleries = []

    for gallery_dir in sorted(dc_dir.iterdir()):
        if not gallery_dir.is_dir() or gallery_dir.name.startswith('example'):
            continue
        json_files = sorted(gallery_dir.glob('*.json'))
        if not json_files:
            continue

        # Read latest file
        latest = json_files[-1]
        try:
            with open(latest, 'r', encoding='utf-8') as f:
                data = json.load(f)

            name = data.get('gallery_name', gallery_dir.name)
            items = _extract_sentiment_items(data, include_content=False)

            sentiment = analyzer.analyze(items)
            s = sentiment['sentiment']
            total = s['positive'] + s['neutral'] + s['negative']
            galleries.append({
                'id': gallery_dir.name,
                'name': name,
                'total': total,
                'positive': s['positive'],
                'neutral': s['neutral'],
                'negative': s['negative'],
                'pos_pct': round(s['positive'] / total * 100) if total else 0,
                'neg_pct': round(s['negative'] / total * 100) if total else 0,
                'keywords': [k['word'] for k in sentiment.get('top_keywords', [])[:5]],
            })
        except Exception as e:
            logger.warning("Compare: failed to process %s: %s", gallery_dir.name, e)

    return jsonify({'galleries': galleries})


@analysis_bp.route('/api/analysis/report/generate-daily', methods=['POST'])
@limiter.limit("2 per minute")
@csrf_protect
@require_analysis_auth
def generate_daily_report():
    """Generate a daily sentiment report for all galleries.

    Saves to local-data/analysis/reports/YYYY-MM-DD.json
    Can be triggered by cron or manually.
    """
    from ..services.sentiment_analyzer import SentimentAnalyzer

    data_dir = _get_local_data_dir()
    analyzer = SentimentAnalyzer()
    dc_dir = data_dir / 'dcinside'

    today = datetime.now().strftime('%Y-%m-%d')
    galleries_report = []

    for gallery_dir in sorted(dc_dir.iterdir()):
        if not gallery_dir.is_dir() or gallery_dir.name.startswith('example'):
            continue
        json_files = sorted(gallery_dir.glob('*.json'))
        if not json_files:
            continue

        # Today's files only
        today_files = [f for f in json_files if f.stem.startswith(today)]
        target_files = today_files if today_files else json_files[-3:]  # fallback to latest 3

        all_items = []
        for jf in target_files:
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    fdata = json.load(f)
                all_items.extend(_extract_sentiment_items(fdata))
            except Exception as e:
                logger.debug("Failed to load posts from %s: %s", jf, e)

        if not all_items:
            continue

        name = gallery_dir.name
        try:
            with open(json_files[-1], 'r', encoding='utf-8') as f:
                name = json.load(f).get('gallery_name', name)
        except Exception as e:
            logger.debug("Could not read gallery name from %s: %s", json_files[-1], e)

        sentiment = analyzer.analyze(all_items)
        s = sentiment['sentiment']
        total = s['positive'] + s['neutral'] + s['negative']

        galleries_report.append({
            'id': gallery_dir.name,
            'name': name,
            'total': total,
            'positive': s['positive'],
            'neutral': s['neutral'],
            'negative': s['negative'],
            'pos_pct': round(s['positive'] / total * 100) if total else 0,
            'neg_pct': round(s['negative'] / total * 100) if total else 0,
            'keywords': [k['word'] for k in sentiment.get('top_keywords', [])[:10]],
            'files_analyzed': len(target_files),
        })

    # Build report
    total_items = sum(g['total'] for g in galleries_report)
    total_pos = sum(g['positive'] for g in galleries_report)
    total_neg = sum(g['negative'] for g in galleries_report)
    alerts = [g for g in galleries_report if g['neg_pct'] >= 5]

    report = {
        'date': today,
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_items': total_items,
            'total_positive': total_pos,
            'total_negative': total_neg,
            'total_galleries': len(galleries_report),
            'pos_pct': round(total_pos / total_items * 100) if total_items else 0,
            'neg_pct': round(total_neg / total_items * 100) if total_items else 0,
            'alerts': len(alerts),
        },
        'galleries': galleries_report,
        'alerts': alerts,
    }

    # Save report
    report_dir = data_dir / 'analysis' / 'reports'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f'{today}.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("Daily report generated: %s (%d galleries, %d items)", today, len(galleries_report), total_items)
    return jsonify(report)


@analysis_bp.route('/api/analysis/reports', methods=['GET'])
@limiter.limit("30 per minute")
def list_reports():
    """List available daily reports."""
    report_dir = _get_local_data_dir() / 'analysis' / 'reports'
    if not report_dir.exists():
        return jsonify({'reports': []})

    reports = []
    for f in sorted(report_dir.glob('*.json'), reverse=True)[:30]:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            reports.append({
                'date': data.get('date', f.stem),
                'summary': data.get('summary', {}),
            })
        except Exception as e:
            logger.debug("Could not read report file %s: %s", f, e)

    return jsonify({'reports': reports})


@analysis_bp.route('/api/analysis/reports/<date>', methods=['GET'])
@limiter.limit("30 per minute")
def get_report(date):
    """Get a specific daily report."""
    if not _SAFE_ID_RE.match(date):
        return jsonify({'error': 'Invalid date'}), 400
    report_file = _get_local_data_dir() / 'analysis' / 'reports' / f'{date}.json'
    if not report_file.exists():
        return jsonify({'error': 'Report not found'}), 404
    with open(report_file, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


# LLM routes (status / summary / chat) live in analysis_llm.py.
