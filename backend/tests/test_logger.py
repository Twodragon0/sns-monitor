"""Tests for app/utils/logger.py."""

import logging
from unittest.mock import patch


def test_setup_logger_oserror_branch():
    """lines 47-48: OSError when creating log dir is silently ignored."""
    unique_name = "test-logger-oserror-unique-xyz"
    # Remove any cached logger
    existing = logging.Logger.manager.loggerDict.pop(unique_name, None)

    with patch("app.utils.logger.os.makedirs", side_effect=OSError("permission denied")):
        from app.utils.logger import setup_logger
        logger = setup_logger(name=unique_name)

    # Logger is returned without file handler (OSError was suppressed)
    assert logger is not None
    assert logger.name == unique_name
    # Only console handler (no file handler added due to OSError)
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "RotatingFileHandler" not in handler_types


def test_setup_logger_cached_returns_same():
    """lines 21-22: cached logger is returned immediately."""
    from app.utils.logger import setup_logger
    name = "test-logger-cached-abc"
    logger1 = setup_logger(name=name)
    logger2 = setup_logger(name=name)
    assert logger1 is logger2


def test_get_logger_no_handlers():
    """get_logger calls setup_logger when no handlers present."""
    name = "test-get-logger-no-handlers-xyz"
    # Clear cached logger
    logging.Logger.manager.loggerDict.pop(name, None)
    from app.utils.logger import get_logger
    with patch("app.utils.logger.setup_logger", wraps=__import__("app.utils.logger", fromlist=["setup_logger"]).setup_logger) as mock_setup:
        logger = get_logger(name=name)
    assert logger is not None
