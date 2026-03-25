"""
DCInside API routes.
Thin wrappers around legacy api_handlers functions.
"""

from . import dcinside_bp
from .legacy_helpers import get_handlers, legacy_response, build_event


@dcinside_bp.route('/api/dcinside/galleries', methods=['GET'])
def galleries():
    return legacy_response(get_handlers()._handle_dcinside_galleries())


@dcinside_bp.route('/api/dcinside/gallery/<gallery_id>/posts', methods=['GET'])
def gallery_posts(gallery_id):
    event = build_event()
    path = f'/api/dcinside/gallery/{gallery_id}/posts'
    return legacy_response(get_handlers()._handle_dcinside_gallery_posts(event, path))
