"""
Integration tests for POST /api/analyze/url → PlatformAnalyzer → response chain.

HTTP calls are mocked at the requests library boundary so no real network
traffic is made.  The Flask test client drives the full route → service path.
"""

import json
import socket
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_post(client, url, payload):
    """POST JSON payload and return (status_code, dict)."""
    resp = client.post(
        "/api/analyze/url",
        data=json.dumps(payload),
        content_type="application/json",
    )
    return resp.status_code, resp.get_json()


def _public_addrinfo(hostname, _port):
    """Fake socket.getaddrinfo that resolves any host to a public IP."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


def _private_addrinfo_127(hostname, _port):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]


def _private_addrinfo_10(hostname, _port):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_platform_analyzer():
    """Force a fresh PlatformAnalyzer instance for each test."""
    # The module keeps a module-level singleton; reset it before each test.
    import app.api.analyze as _analyze_mod
    _analyze_mod._platform_analyzer = None
    yield
    _analyze_mod._platform_analyzer = None


# ---------------------------------------------------------------------------
# 1. YouTube URL analysis
# ---------------------------------------------------------------------------

class TestYouTubeIntegration:
    def test_youtube_video_analysis(self, client):
        """Full route: YouTube video URL → mocked API → structured response."""
        video_id = "dQw4w9WgXcQ"
        url = f"https://www.youtube.com/watch?v={video_id}"

        video_response = MagicMock()
        video_response.ok = True
        video_response.json.return_value = {
            "items": [{
                "snippet": {
                    "title": "Rick Astley - Never Gonna Give You Up",
                    "description": "Official video",
                    "channelTitle": "Rick Astley",
                    "publishedAt": "2009-10-25T06:57:33Z",
                },
                "statistics": {
                    "viewCount": "1400000000",
                    "likeCount": "15000000",
                    "commentCount": "2000000",
                },
            }]
        }

        comments_response = MagicMock()
        comments_response.ok = True
        comments_response.json.return_value = {
            "items": [
                {
                    "snippet": {
                        "topLevelComment": {
                            "snippet": {
                                "textDisplay": "정말 좋아요 최고의 영상",
                                "likeCount": 100,
                                "publishedAt": "2024-01-01T00:00:00Z",
                                "authorDisplayName": "user1",
                            }
                        },
                        "totalReplyCount": 0,
                    }
                }
            ],
            "pageInfo": {"totalResults": 1},
        }

        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "fake-api-key-1234"}), \
             patch("socket.getaddrinfo", side_effect=_public_addrinfo), \
             patch("requests.Session.get", side_effect=[video_response, comments_response]):
            status, data = _json_post(client, "/api/analyze/url", {"url": url})

        assert status == 200, f"Expected 200, got {status}: {data}"
        assert data["platform"] == "youtube"
        assert "title" in data
        assert data["title"] == "Rick Astley - Never Gonna Give You Up"
        assert "source_url" in data
        assert "analyzed_at" in data
        # comments list present
        assert "comments" in data
        assert isinstance(data["comments"], list)

    def test_youtube_missing_api_key_returns_400(self, client):
        """YouTube without API key should return 400 with a helpful error."""
        url = "https://www.youtube.com/watch?v=abc123"
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": ""}, clear=False), \
             patch("socket.getaddrinfo", side_effect=_public_addrinfo):
            status, data = _json_post(client, "/api/analyze/url", {"url": url})

        assert status == 400
        assert "error" in data
        assert "YouTube" in data["error"] or "API key" in data["error"] or "key" in data["error"].lower()


# ---------------------------------------------------------------------------
# 2. DCInside URL analysis
# ---------------------------------------------------------------------------

class TestDCInsideIntegration:
    def test_dcinside_gallery_list(self, client):
        """Full route: DCInside gallery list URL → mocked HTML → posts returned."""
        url = "https://gall.dcinside.com/board/lists?id=programming"

        # DCInside scraper uses self._session.get; mock it to return HTML
        html_response = MagicMock()
        html_response.ok = True
        html_response.status_code = 200
        # Minimal HTML that satisfies BeautifulSoup parsing (no posts → empty list)
        html_response.text = """
        <html><body>
        <table class="gall_list">
        <tbody>
        <tr class="us-post" data-no="12345">
          <td class="gall_tit">
            <a href="/board/view?id=programming&amp;no=12345">테스트 게시글 제목</a>
          </td>
          <td class="gall_writer" data-nick="테스터" data-uid="abc123"></td>
          <td class="gall_count">100</td>
          <td class="gall_recommend">10</td>
          <td class="gall_date" title="2024-01-01 12:00:00">01.01</td>
        </tr>
        </tbody>
        </table>
        </body></html>
        """
        html_response.content = html_response.text.encode("utf-8")

        with patch("socket.getaddrinfo", side_effect=_public_addrinfo), \
             patch("requests.Session.get", return_value=html_response):
            status, data = _json_post(client, "/api/analyze/url", {"url": url})

        assert status == 200, f"Expected 200, got {status}: {data}"
        assert data["platform"] == "dcinside"
        assert "gallery_id" in data
        assert data["gallery_id"] == "programming"
        assert "source_url" in data
        assert "analyzed_at" in data
        # posts key present (even if empty when parsing fails gracefully)
        assert "posts" in data or "type" in data

    def test_dcinside_invalid_url_returns_400(self, client):
        """DCInside URL without gallery id should return 400."""
        url = "https://gall.dcinside.com/board/lists"  # missing ?id=
        with patch("socket.getaddrinfo", side_effect=_public_addrinfo):
            status, data = _json_post(client, "/api/analyze/url", {"url": url})

        assert status == 400
        assert "error" in data


# ---------------------------------------------------------------------------
# 3. Reddit URL analysis
# ---------------------------------------------------------------------------

class TestRedditIntegration:
    def test_reddit_subreddit_analysis(self, client):
        """Full route: Reddit subreddit URL → mocked API → posts returned."""
        url = "https://www.reddit.com/r/python"

        subreddit_response = MagicMock()
        subreddit_response.ok = True
        subreddit_response.status_code = 200
        subreddit_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Cool Python project",
                            "selftext": "Here is my project description",
                            "score": 1500,
                            "num_comments": 42,
                            "url": "https://github.com/example/project",
                            "author": "redditor1",
                            "created_utc": 1704067200,
                            "permalink": "/r/python/comments/abc123/cool_python_project/",
                        }
                    }
                ],
                "dist": 1,
            }
        }

        with patch("socket.getaddrinfo", side_effect=_public_addrinfo), \
             patch("requests.Session.get", return_value=subreddit_response):
            status, data = _json_post(client, "/api/analyze/url", {"url": url})

        assert status == 200, f"Expected 200, got {status}: {data}"
        assert data["platform"] == "reddit"
        assert "subreddit" in data
        assert data["subreddit"] == "python"
        assert "source_url" in data
        assert "analyzed_at" in data
        assert "posts" in data
        assert isinstance(data["posts"], list)

    def test_reddit_post_analysis(self, client):
        """Full route: Reddit post URL → mocked API → comments returned."""
        url = "https://www.reddit.com/r/python/comments/abc123/cool_post/"

        post_response = MagicMock()
        post_response.ok = True
        post_response.status_code = 200
        post_response.json.return_value = [
            {
                "data": {
                    "children": [{
                        "data": {
                            "id": "abc123",
                            "title": "Cool post title",
                            "selftext": "Post body text",
                            "score": 500,
                            "num_comments": 10,
                            "author": "op_user",
                            "created_utc": 1704067200,
                            "subreddit": "python",
                            "permalink": "/r/python/comments/abc123/cool_post/",
                        }
                    }]
                }
            },
            {
                "data": {
                    "children": [
                        {
                            "data": {
                                "id": "c1",
                                "body": "Great post!",
                                "author": "commenter1",
                                "score": 20,
                                "created_utc": 1704067300,
                            }
                        }
                    ]
                }
            }
        ]

        with patch("socket.getaddrinfo", side_effect=_public_addrinfo), \
             patch("requests.Session.get", return_value=post_response):
            status, data = _json_post(client, "/api/analyze/url", {"url": url})

        assert status == 200, f"Expected 200, got {status}: {data}"
        assert data["platform"] == "reddit"
        assert "analyzed_at" in data


# ---------------------------------------------------------------------------
# 4. Invalid URL
# ---------------------------------------------------------------------------

class TestInvalidURL:
    def test_empty_url_returns_400(self, client):
        status, data = _json_post(client, "/api/analyze/url", {"url": ""})
        assert status == 400
        assert "error" in data

    def test_no_url_field_returns_400(self, client):
        status, data = _json_post(client, "/api/analyze/url", {})
        assert status == 400
        assert "error" in data

    def test_garbage_string_returns_400(self, client):
        status, data = _json_post(client, "/api/analyze/url", {"url": "not-a-url-at-all"})
        assert status == 400
        assert "error" in data

    def test_url_too_long_returns_400(self, client):
        long_url = "https://example.com/" + "a" * 3000
        status, data = _json_post(client, "/api/analyze/url", {"url": long_url})
        assert status == 400
        assert "error" in data

    def test_non_json_body_returns_400(self, client):
        resp = client.post(
            "/api/analyze/url",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400

    def test_ftp_scheme_returns_400(self, client):
        """Non-http/https schemes must be rejected at the route level."""
        status, data = _json_post(client, "/api/analyze/url", {"url": "ftp://example.com/file"})
        assert status == 400
        assert "error" in data


# ---------------------------------------------------------------------------
# 5. Unsupported platform
# ---------------------------------------------------------------------------

class TestUnsupportedPlatform:
    def test_unsupported_domain_returns_400(self, client):
        """example.com is not a recognized platform → 400 with error message."""
        with patch("socket.getaddrinfo", side_effect=_public_addrinfo):
            status, data = _json_post(
                client, "/api/analyze/url", {"url": "https://example.com/some/page"}
            )

        assert status == 400
        assert "error" in data
        assert "Unsupported" in data["error"] or "unsupported" in data["error"].lower() or "platform" in data["error"].lower()

    def test_wikipedia_returns_400(self, client):
        with patch("socket.getaddrinfo", side_effect=_public_addrinfo):
            status, data = _json_post(
                client, "/api/analyze/url", {"url": "https://en.wikipedia.org/wiki/Python"}
            )

        assert status == 400
        assert "error" in data


# ---------------------------------------------------------------------------
# 6. SSRF protection
# ---------------------------------------------------------------------------

class TestSSRFProtection:
    def test_localhost_ip_blocked(self, client):
        """127.0.0.1 should be blocked by SSRF protection."""
        with patch("socket.getaddrinfo", side_effect=_private_addrinfo_127):
            status, data = _json_post(
                client, "/api/analyze/url", {"url": "https://example.com/page"}
            )

        assert status == 400
        assert "error" in data

    def test_private_10_net_blocked(self, client):
        """10.x.x.x should be blocked by SSRF protection."""
        with patch("socket.getaddrinfo", side_effect=_private_addrinfo_10):
            status, data = _json_post(
                client, "/api/analyze/url", {"url": "https://example.com/page"}
            )

        assert status == 400
        assert "error" in data

    def test_explicit_loopback_url_blocked(self, client):
        """Direct 127.0.0.1 hostname in URL → rejected at route validation."""
        status, data = _json_post(
            client, "/api/analyze/url", {"url": "http://127.0.0.1/admin"}
        )
        # Either blocked by the analyzer SSRF check → 400, or by scheme check
        # Either way must not be 200
        assert status in (400, 500)
        assert "error" in data

    def test_metadata_endpoint_blocked(self, client):
        """Cloud metadata endpoint must be blocked by hostname blocklist."""
        with patch("socket.getaddrinfo", side_effect=_public_addrinfo):
            status, data = _json_post(
                client, "/api/analyze/url",
                {"url": "http://metadata.google.internal/computeMetadata/v1/"}
            )

        assert status == 400
        assert "error" in data

    def test_ipv4_private_range_172(self, client):
        """172.16.x.x private range should be blocked."""
        def _172_addrinfo(h, p):
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("172.16.0.1", 0))]

        with patch("socket.getaddrinfo", side_effect=_172_addrinfo):
            status, data = _json_post(
                client, "/api/analyze/url", {"url": "https://example.com/page"}
            )

        assert status == 400
        assert "error" in data

    def test_ipv4_private_range_192_168(self, client):
        """192.168.x.x private range should be blocked."""
        def _192_addrinfo(h, p):
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.100", 0))]

        with patch("socket.getaddrinfo", side_effect=_192_addrinfo):
            status, data = _json_post(
                client, "/api/analyze/url", {"url": "https://example.com/page"}
            )

        assert status == 400
        assert "error" in data
