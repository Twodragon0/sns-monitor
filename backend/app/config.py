"""
Centralized configuration management.
All environment variables are accessed through this class.
"""

import os


class Config:
    """Flask and application configuration."""

    # Flask
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # API
    API_PORT = int(os.environ.get('API_PORT', 8080))

    # Storage
    LOCAL_MODE = os.environ.get('LOCAL_MODE', 'true').lower() == 'true'
    LOCAL_DATA_DIR = os.environ.get('LOCAL_DATA_DIR', './local-data')

    # Redis (optional)
    REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

    # YouTube
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')

    # AWS (only used when LOCAL_MODE=false)
    S3_BUCKET = os.environ.get('S3_BUCKET', '')
    DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', '')

    # JSON encoding
    JSON_AS_ASCII = False

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        errors = []
        if not cls.YOUTUBE_API_KEY:
            errors.append("YOUTUBE_API_KEY is not set")
        return errors
