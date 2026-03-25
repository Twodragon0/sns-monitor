"""
Data, Crawler results, and Twitter search API routes.
Thin wrappers around legacy api_handlers functions.
"""

from . import data_bp
from .legacy_helpers import get_handlers, legacy_response, build_event


@data_bp.route('/api/data/<path:s3_key>', methods=['GET'])
def get_data(s3_key):
    path = f'/api/data/{s3_key}'
    return legacy_response(get_handlers()._handle_data_s3_key(path))


@data_bp.route('/api/crawler/results', methods=['POST'])
def crawler_results():
    event = build_event()
    return legacy_response(get_handlers()._handle_crawler_results(event))


@data_bp.route('/api/twitter/search', methods=['POST'])
def twitter_search():
    event = build_event()
    return legacy_response(get_handlers()._handle_twitter_search(event))
