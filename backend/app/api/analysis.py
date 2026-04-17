"""
SNS AI Analysis Bridge API.
Transforms SNS crawled data into documents and proxies analysis requests to the AI analysis service.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from flask import request, jsonify, session

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

MIROFISH_URL = os.environ.get('MIROFISH_ENDPOINT', 'http://mirofish:5001')


def _validate_chat_history(data):
    """Validate and sanitize chat_history from request data.

    Returns a validated list of message dicts, or a Flask error response tuple
    (jsonify(...), status_code) if the raw value is not a list.
    Callers must check: if isinstance(result, tuple): return result
    """
    raw_history = data.get('chat_history', [])
    if not isinstance(raw_history, list):
        return jsonify({'error': 'Invalid chat_history format'}), 400
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


def _proxy_json(resp):
    """Safely extract JSON from a proxied response, returning a Flask tuple."""
    try:
        return jsonify(resp.json()), resp.status_code
    except (ValueError, requests.exceptions.JSONDecodeError):
        logger.warning("MiroFish returned non-JSON (status %d): %s", resp.status_code, resp.text[:200])
        return jsonify({'error': 'Invalid response from AI analysis service'}), 502


def _mirofish_headers():
    """Forward OpenAI OAuth access token to AI analysis service so it can call OpenAI API without LLM_API_KEY."""
    headers = {}
    token = session.get('access_token')
    # Validate: must be a non-empty ASCII string with no control characters (header-injection guard).
    if isinstance(token, str) and token.strip() and all(c >= ' ' and c <= '~' for c in token):
        headers['Authorization'] = f'Bearer {token}'
        headers['X-OpenAI-Access-Token'] = token  # service can use either header
    elif token is not None:
        logger.warning("Ignoring invalid access_token type in session: %s", type(token).__name__)
    return headers


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

    Returns (documents: list[str], error_response: tuple|None).
    If error_response is not None, caller should return it directly.
    """
    documents = []
    for src in sources_list:
        src_type = src.get('type', '')
        src_id = src.get('id', '')
        if not _SAFE_ID_RE.match(src_id):
            return [], (jsonify({'error': 'Invalid source id'}), 400)

        if src_type == 'youtube':
            doc = _transform_youtube_to_document(src_id)
        elif src_type == 'dcinside':
            doc = _transform_dcinside_to_document(src_id)
        else:
            continue

        if doc:
            documents.append(doc)

    return documents, None


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


@analysis_bp.route('/api/analysis/status', methods=['GET'])
@limiter.limit("30 per minute")
def analysis_status():
    """Check AI analysis service availability."""
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/project/list',
            timeout=5,
            headers=_mirofish_headers(),
        )
        available = resp.status_code == 200
    except Exception:
        available = False

    return jsonify({
        'mirofish_available': available,
        'mirofish_endpoint': MIROFISH_URL
    })


@analysis_bp.route('/api/analysis/transform', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
@require_analysis_auth
def transform_sns_data():
    """
    Transform SNS crawled data into a document and send to AI analysis service.

    Request JSON:
    {
        "sources": [
            {"type": "youtube", "id": "example-creator-1"},
            {"type": "dcinside", "id": "example-gallery-1"}
        ],
        "project_name": "SNS Analysis - Jan 2025",
        "simulation_requirement": "Analyze community sentiment trends and predict reactions"
    }
    """
    data = request.get_json() or {}
    sources = data.get('sources', [])
    project_name = data.get('project_name', f'SNS Analysis - {datetime.now().strftime("%Y-%m-%d")}')
    simulation_requirement = data.get('simulation_requirement',
        'Analyze social media community sentiment, identify key trends, and predict audience reactions')

    if not sources:
        return jsonify({'error': 'No data sources specified'}), 400

    # Transform each source to Markdown document
    documents = []
    for src in sources:
        src_type = src.get('type')
        src_id = src.get('id', '')
        if not _SAFE_ID_RE.match(src_id):
            return jsonify({'error': f'Invalid source id'}), 400

        if src_type == 'youtube':
            doc = _transform_youtube_to_document(src_id)
        elif src_type == 'dcinside':
            doc = _transform_dcinside_to_document(src_id)
        else:
            continue

        if doc:
            documents.append({
                'filename': f'{src_type}_{src_id}.md',
                'content': doc
            })

    if not documents:
        return jsonify({'error': 'No data found for specified sources'}), 404

    # Send to AI analysis service as file upload
    import tempfile
    files = []
    temp_files = []
    try:
        for doc in documents:
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
            tmp.write(doc['content'])
            tmp.close()
            temp_files.append(tmp.name)
            files.append(('files', (doc['filename'], open(tmp.name, 'rb'), 'text/markdown')))

        resp = requests.post(
            f'{MIROFISH_URL}/api/graph/ontology/generate',
            data={
                'simulation_requirement': simulation_requirement,
                'project_name': project_name,
            },
            files=files,
            timeout=120,
            headers=_mirofish_headers(),
        )

        if resp.status_code != 200:
            logger.warning("MiroFish returned %d: %s", resp.status_code, resp.text[:200])
        try:
            result = resp.json()
        except ValueError:
            return jsonify({'error': 'Invalid response from AI analysis service'}), 502
        return jsonify(result), resp.status_code

    except requests.ConnectionError:
        return jsonify({
            'error': 'AI analysis service not available. Start with: docker-compose --profile analysis up -d'
        }), 503
    except Exception as e:
        logger.error("AI analysis transform failed: %s", e, exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        for f_tuple in files:
            try:
                f_tuple[1][1].close()
            except Exception:
                pass
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@analysis_bp.route('/api/analysis/graph/build', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
@require_analysis_auth
def build_analysis_graph():
    """Proxy graph build request to AI analysis service."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/graph/build',
            json=request.get_json(),
            timeout=30,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/graph/task/<task_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_analysis_auth
def get_analysis_task(task_id):
    """Proxy task status query to AI analysis service."""
    if not _SAFE_ID_RE.match(task_id):
        return jsonify({'error': 'Invalid task_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/task/{task_id}',
            timeout=10,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/graph/data/<graph_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_analysis_auth
def get_analysis_graph_data(graph_id):
    """Proxy graph data query to AI analysis service."""
    if not _SAFE_ID_RE.match(graph_id):
        return jsonify({'error': 'Invalid graph_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/data/{graph_id}',
            timeout=30,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/report/generate', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
@require_analysis_auth
def generate_analysis_report():
    """Proxy report generation to AI analysis service."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/report/generate',
            json=request.get_json(),
            timeout=30,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/report/<report_id>', methods=['GET'])
@limiter.limit("30 per minute")
@require_analysis_auth
def get_analysis_report(report_id):
    """Proxy report retrieval from AI analysis service."""
    if not _SAFE_ID_RE.match(report_id):
        return jsonify({'error': 'Invalid report_id'}), 400
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/report/{report_id}',
            timeout=30,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/report/chat', methods=['POST'])
@limiter.limit("20 per minute")
@csrf_protect
@require_analysis_auth
def chat_with_analysis():
    """Proxy chat with AI analysis ReportAgent."""
    try:
        resp = requests.post(
            f'{MIROFISH_URL}/api/report/chat',
            json=request.get_json(),
            timeout=60,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


@analysis_bp.route('/api/analysis/projects', methods=['GET'])
@limiter.limit("30 per minute")
@require_analysis_auth
def list_analysis_projects():
    """Proxy project list from AI analysis service."""
    try:
        resp = requests.get(
            f'{MIROFISH_URL}/api/graph/project/list',
            timeout=10,
            headers=_mirofish_headers(),
        )
        return _proxy_json(resp)
    except requests.ConnectionError:
        return jsonify({'error': 'AI analysis service not available'}), 503


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


def _session_llm_kwargs():
    """Extract LLM credentials from Flask session."""
    return {
        'oauth_token': session.get('access_token'),
        'token_provider': session.get('token_provider'),
        'session_api_key': session.get('session_api_key'),
        'session_api_provider': session.get('session_api_provider'),
    }


@analysis_bp.route('/api/analysis/llm/status', methods=['GET'])
def llm_status():
    """Check local LLM availability (Claude / OpenAI / OAuth)."""
    from ..services.llm_analyzer import get_llm_status
    status = get_llm_status(**_session_llm_kwargs())
    return jsonify(status)


@analysis_bp.route('/api/analysis/ai-summary', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
def ai_summary():
    """
    AI-powered analysis using local LLM (Claude or ChatGPT).
    Works standalone — calls LLM APIs directly.

    Request JSON:
    {
        "sources": [{"type": "youtube", "id": "channel-handle"}, ...],
        "question": "optional specific question"
    }
    """
    from ..services.llm_analyzer import analyze_with_llm, get_available_provider

    provider = get_available_provider(**_session_llm_kwargs())
    if not provider:
        return jsonify({
            'error': 'LLM 인증이 필요합니다. Anthropic OAuth 로그인 또는 API Key를 입력하세요.'
        }), 503

    data = request.get_json() or {}
    sources_list = data.get('sources', [])
    question = data.get('question', '')

    if not sources_list:
        return jsonify({'error': 'No data sources specified'}), 400

    documents, err = _build_documents_from_sources(sources_list)
    if err:
        return err
    if not documents:
        return jsonify({'error': 'No data found for specified sources'}), 404

    full_document = '\n\n---\n\n'.join(documents)
    result = analyze_with_llm(full_document, question if question else None, **_session_llm_kwargs())

    if 'error' in result and not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)


@analysis_bp.route('/api/analysis/ai-chat', methods=['POST'])
@limiter.limit("20 per minute")
@csrf_protect
def ai_chat():
    """
    Chat with local LLM about SNS data.

    Request JSON:
    {
        "sources": [{"type": "youtube", "id": "channel-handle"}, ...],
        "message": "user question",
        "chat_history": [{"role": "user", "content": "..."}, ...]
    }
    """
    from ..services.llm_analyzer import chat_with_llm, get_available_provider

    provider = get_available_provider(**_session_llm_kwargs())
    if not provider:
        return jsonify({'error': 'LLM 인증이 필요합니다. OAuth 로그인 또는 API Key를 입력하세요.'}), 503

    data = request.get_json() or {}
    sources_list = data.get('sources', [])
    message = (data.get('message') or '').strip()

    chat_history = _validate_chat_history(data)
    if isinstance(chat_history, tuple):
        return chat_history

    if not message:
        return jsonify({'error': 'Message is required'}), 400
    if len(message) > 5000:
        return jsonify({'error': 'Message exceeds maximum length of 5000 characters'}), 400
    if not sources_list:
        return jsonify({'error': 'No data sources specified'}), 400

    documents, err = _build_documents_from_sources(sources_list)
    if err:
        return err
    if not documents:
        return jsonify({'error': 'No data found for specified sources'}), 404

    full_document = '\n\n---\n\n'.join(documents)
    result = chat_with_llm(full_document, message, chat_history, **_session_llm_kwargs())

    if 'error' in result and not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)


@analysis_bp.route('/api/analysis/ai-url-analyze', methods=['POST'])
@limiter.limit("5 per minute")
@csrf_protect
def ai_url_analyze():
    """
    AI analysis of URL analyzer results (direct pass-through from URLAnalyzer).
    Accepts pre-built analysis result and sends to LLM for deep analysis.

    Request JSON:
    {
        "result": { ... URL analyzer result ... },
        "question": "optional question"
    }
    """
    from ..services.llm_analyzer import analyze_with_llm, get_available_provider

    provider = get_available_provider(**_session_llm_kwargs())
    if not provider:
        return jsonify({
            'error': 'No LLM available. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, or login with OAuth.'
        }), 503

    data = request.get_json() or {}
    url_result = data.get('result')
    question = data.get('question', '')

    if not url_result:
        return jsonify({'error': 'Analysis result is required'}), 400

    document = _build_document_from_url_result(url_result)
    result = analyze_with_llm(document, question if question else None, **_session_llm_kwargs())

    if 'error' in result and not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)


@analysis_bp.route('/api/analysis/ai-url-chat', methods=['POST'])
@limiter.limit("20 per minute")
@csrf_protect
def ai_url_chat():
    """
    Chat about URL analysis results with LLM.

    Request JSON:
    {
        "result": { ... URL analyzer result ... },
        "message": "user question",
        "chat_history": [...]
    }
    """
    from ..services.llm_analyzer import chat_with_llm, get_available_provider

    oauth_token = session.get('access_token')
    provider = get_available_provider(oauth_token=oauth_token)
    if not provider:
        return jsonify({'error': 'No LLM available'}), 503

    data = request.get_json() or {}
    url_result = data.get('result')
    message = (data.get('message') or '').strip()

    chat_history = _validate_chat_history(data)
    if isinstance(chat_history, tuple):
        return chat_history

    if not message:
        return jsonify({'error': 'Message is required'}), 400
    if len(message) > 5000:
        return jsonify({'error': 'Message exceeds maximum length of 5000 characters'}), 400
    if not url_result:
        return jsonify({'error': 'Analysis result is required'}), 400

    document = _build_document_from_url_result(url_result, compact=True)
    result = chat_with_llm(document, message, chat_history, **_session_llm_kwargs())

    if 'error' in result and not result.get('success'):
        return jsonify(result), 500

    return jsonify(result)
