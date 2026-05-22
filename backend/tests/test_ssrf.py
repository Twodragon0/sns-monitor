"""Tests for SSRF protection in PlatformAnalyzer._validate_url_host."""

import pytest
from unittest.mock import patch
from app.services.platform_analyzer import PlatformAnalyzer


class TestValidateUrlHost:
    """Tests for _validate_url_host SSRF protection."""

    def test_blocks_metadata_google_internal(self):
        with pytest.raises(ValueError, match="Blocked host"):
            PlatformAnalyzer._validate_url_host("http://metadata.google.internal/")

    def test_blocks_metadata_google_com(self):
        with pytest.raises(ValueError, match="Blocked host"):
            PlatformAnalyzer._validate_url_host("http://metadata.google.com/")

    def test_blocks_localhost_ip(self):
        with pytest.raises(ValueError, match="Internal"):
            PlatformAnalyzer._validate_url_host("http://127.0.0.1/")

    def test_blocks_private_ip_10(self):
        with pytest.raises(ValueError, match="Internal"):
            PlatformAnalyzer._validate_url_host("http://10.0.0.1/")

    def test_blocks_private_ip_192(self):
        with pytest.raises(ValueError, match="Internal"):
            PlatformAnalyzer._validate_url_host("http://192.168.1.1/")

    def test_blocks_link_local(self):
        with pytest.raises(ValueError, match="Internal"):
            PlatformAnalyzer._validate_url_host("http://169.254.169.254/")

    @patch('app.services.platform_analyzer.socket.getaddrinfo')
    def test_blocks_dns_rebinding_to_private(self, mock_getaddrinfo):
        """DNS rebinding: hostname resolves to private IP should be blocked."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, '', ('169.254.169.254', 0)),
        ]
        with pytest.raises(ValueError, match="Internal"):
            PlatformAnalyzer._validate_url_host("http://evil-rebind.example.com/")

    @patch('app.services.platform_analyzer.socket.getaddrinfo')
    def test_allows_public_ip(self, mock_getaddrinfo):
        """Public IPs should pass validation."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, '', ('142.250.80.46', 0)),
        ]
        # Should not raise
        PlatformAnalyzer._validate_url_host("https://www.google.com/")

    def test_blocks_missing_hostname(self):
        with pytest.raises(ValueError, match="missing hostname"):
            PlatformAnalyzer._validate_url_host("http:///path")

    @patch('app.services.platform_analyzer.socket.getaddrinfo')
    def test_blocks_unresolvable_hostname(self, mock_getaddrinfo):
        import socket
        mock_getaddrinfo.side_effect = socket.gaierror("Name resolution failed")
        with pytest.raises(ValueError, match="Cannot resolve hostname"):
            PlatformAnalyzer._validate_url_host("http://nonexistent.invalid/")


class TestDnsPinning:
    """Validate that validate-then-pin closes the DNS rebinding TOCTOU window."""

    @patch('app.services.platform_analyzer.socket.getaddrinfo')
    def test_validate_returns_hostname_and_primary_ip(self, mock_getaddrinfo):
        import socket as _s
        mock_getaddrinfo.return_value = [
            (_s.AF_INET, _s.SOCK_STREAM, 6, '', ('8.8.8.8', 0))
        ]
        host, ip = PlatformAnalyzer._validate_url_host('https://example.com/x')
        assert host == 'example.com'
        assert ip == '8.8.8.8'

    def test_pin_dns_context_overrides_resolution(self):
        import socket as _s
        from app.services.platform_analyzer import _pin_dns, _pinned_getaddrinfo
        with _pin_dns('example.com', '203.0.113.7'):
            info = _pinned_getaddrinfo('example.com', 443)
            # Delegating to the real getaddrinfo with the pinned IP literal can
            # yield multiple socktype entries (SOCK_STREAM + SOCK_DGRAM).
            # Every entry must still point at the pinned IP, and the result
            # cannot be empty.
            assert info
            for entry in info:
                assert entry[4][0] == '203.0.113.7'
        # After exit, pinning is cleared
        from app.services.platform_analyzer import _pinning_state
        assert getattr(_pinning_state, 'map', {}) in ({}, None)

    def test_pin_dns_falls_through_for_other_hosts(self):
        import socket as _s
        from app.services.platform_analyzer import _pin_dns, _pinned_getaddrinfo
        # Should pass through to original for unrelated hosts; we mock the
        # original to avoid touching the real DNS.
        with patch('app.services.platform_analyzer._orig_getaddrinfo') as orig:
            orig.return_value = [(_s.AF_INET, _s.SOCK_STREAM, 6, '', ('1.1.1.1', 0))]
            with _pin_dns('example.com', '203.0.113.7'):
                info = _pinned_getaddrinfo('cloudflare.com', 443)
            orig.assert_called_once()
            assert info[0][4][0] == '1.1.1.1'
