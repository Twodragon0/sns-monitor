"""
SNS Monitor Backend - Entry Point
"""

import logging
import os
import sys

# Add backend directory to Python path (for api_handlers import)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config

logger = logging.getLogger(__name__)


def main():
    errors = Config.validate()
    if errors:
        logger.warning("Configuration warnings:")
        for err in errors:
            logger.warning("  - %s", err)
        logger.warning("Some features may not work without required API keys.")

    app = create_app()
    app.run(
        host='0.0.0.0',
        port=Config.API_PORT,
        debug=Config.DEBUG,
        threaded=True
    )


if __name__ == '__main__':
    main()
