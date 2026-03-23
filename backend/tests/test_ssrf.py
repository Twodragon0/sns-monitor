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
