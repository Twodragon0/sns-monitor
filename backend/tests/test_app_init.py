"""Tests for app/__init__.py - create_app, health routes, CORS, Redis URI."""

import os
from unittest.mock import MagicMock, patch


class TestBuildRedisUri:
    def test_no_redis_host_returns_memory(self):
        from app import _build_redis_uri
        with patch('app.Config') as mock_cfg:
            mock_cfg.REDIS_HOST = ''
            mock_cfg.REDIS_PASSWORD = ''
            mock_cfg.REDIS_PORT = 6379
            result = _build_redis_uri()
        assert result == 'memory://'

    def test_with_password_includes_password(self):
        from app import _build_redis_uri
        with patch('app.Config') as mock_cfg:
            mock_cfg.REDIS_HOST = 'redis-host'
            mock_cfg.REDIS_PASSWORD = 'secret'
            mock_cfg.REDIS_PORT = 6379
            result = _build_redis_uri()
        assert 'secret' in result
        assert 'redis-host' in result

    def test_without_password_no_credentials(self):
        from app import _build_redis_uri
        with patch('app.Config') as mock_cfg:
            mock_cfg.REDIS_HOST = 'redis-host'
            mock_cfg.REDIS_PASSWORD = ''
            mock_cfg.REDIS_PORT = 6379
            result = _build_redis_uri()
        assert 'redis-host' in result
        assert ':@' not in result


class TestHealthRoutes:
    def test_health_endpoint_ok(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] in ('ok', 'degraded')
        assert data['redis'] in ('connected', 'disconnected')
        assert data['data_dir'] in ('accessible', 'missing')
        assert isinstance(data['uptime_seconds'], int)
        assert 'local_mode' in data

    def test_api_health_endpoint_ok(self, client):
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] in ('ok', 'degraded')

    def test_health_with_redis_ping_true(self, client):
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        with patch('app.services.redis_client.get_redis', return_value=mock_redis):
            resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['redis'] == 'connected'

    def test_health_redis_exception_still_returns_200(self, client):
        with patch('app.services.redis_client.get_redis', side_effect=RuntimeError('no redis')):
            resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] in ('ok', 'degraded')
        assert data['redis'] == 'disconnected'

    def test_health_contains_uptime(self, client):
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['uptime_seconds'] >= 0

    def test_health_data_dir_accessible_when_exists(self, client):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.Config') as mock_cfg:
                mock_cfg.LOCAL_DATA_DIR = tmpdir
                mock_cfg.LOCAL_MODE = True
                resp = client.get('/api/health')
        assert resp.status_code == 200


class TestCreateAppCors:
    def test_cors_origins_env_var_used(self):
        with patch.dict(os.environ, {'CORS_ORIGINS': 'http://example.com', 'REDIS_HOST': '', 'REDIS_PASSWORD': ''}):
            from app import create_app
            app = create_app()
            app.config['TESTING'] = True
            with app.test_client() as c:
                resp = c.get('/api/health')
                assert resp.status_code == 200


class TestConfigValidate:
    def test_validate_returns_error_when_no_api_key(self):
        from app.config import Config
        with patch.object(Config, 'YOUTUBE_API_KEY', ''):
            errors = Config.validate()
        assert len(errors) > 0
        assert any('YOUTUBE_API_KEY' in e for e in errors)

    def test_validate_returns_empty_when_api_key_set(self):
        from app.config import Config
        with patch.object(Config, 'YOUTUBE_API_KEY', 'some-key'):
            errors = Config.validate()
        assert errors == []


class TestRedisClientPassword:
    def test_redis_with_password_sets_password_kwarg(self):
        import importlib
        import app.services.redis_client as rc_module
        # Reset module state
        rc_module._redis_checked = False
        rc_module._redis_client = None

        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis_class = MagicMock(return_value=mock_redis_instance)

        with patch('app.config.Config') as mock_cfg:
            mock_cfg.REDIS_HOST = 'localhost'
            mock_cfg.REDIS_PORT = 6379
            mock_cfg.REDIS_PASSWORD = 'mypassword'
            with patch('redis.Redis', mock_redis_class):
                result = rc_module.get_redis()

        call_kwargs = mock_redis_class.call_args[1]
        assert call_kwargs.get('password') == 'mypassword'
        assert result is mock_redis_instance

        # Restore
        rc_module._redis_checked = False
        rc_module._redis_client = None


class TestLogger:
    def test_setup_logger_oserror_handled(self):
        from app.utils.logger import setup_logger
        with patch('logging.FileHandler', side_effect=OSError('no disk')):
            logger = setup_logger('test-oserror-logger')
        assert logger is not None

    def test_get_logger_returns_existing(self):
        from app.utils.logger import setup_logger, get_logger
        setup_logger('test-existing-logger')
        logger = get_logger('test-existing-logger')
        assert logger is not None

    def test_get_logger_creates_new(self):
        from app.utils.logger import get_logger
        logger = get_logger('test-brand-new-logger-xyz')
        assert logger is not None
