"""
Dashboard API routes.
Thin wrappers around legacy api_handlers functions.
"""

from . import dashboard_bp
from .legacy_helpers import get_handlers, legacy_response, build_event


@dashboard_bp.route('/api/dashboard/stats', methods=['GET'])
def dashboard_stats():
    return legacy_response(get_handlers()._handle_dashboard_stats())


@dashboard_bp.route('/api/scans', methods=['GET'])
def scans():
    return legacy_response(get_handlers()._handle_scans())


@dashboard_bp.route('/api/channels', methods=['GET'])
def channels():
    return legacy_response(get_handlers()._handle_channels())


@dashboard_bp.route('/api/vuddy/creators', methods=['GET'])
def vuddy_creators():
    return legacy_response(get_handlers()._handle_vuddy_creators())


@dashboard_bp.route('/api/group-a/members', methods=['GET'])
def group_a_members():
    return legacy_response(get_handlers()._handle_group_a_members())


@dashboard_bp.route('/api/group-b/members', methods=['GET'])
def group_b_members():
    return legacy_response(get_handlers()._handle_group_b_members())


@dashboard_bp.route('/api/group-c/members', methods=['GET'])
def group_c_members():
    return legacy_response(get_handlers()._handle_group_c_members())


@dashboard_bp.route('/api/group-a/channel', methods=['GET'])
def group_a_channel():
    event = build_event()
    return legacy_response(get_handlers()._handle_group_a_channel(event))


@dashboard_bp.route('/api/group-b/channel', methods=['GET'])
def group_b_channel():
    event = build_event()
    return legacy_response(get_handlers()._handle_group_b_channel(event))


@dashboard_bp.route('/api/group-c/channel', methods=['GET'])
def group_c_channel():
    event = build_event()
    return legacy_response(get_handlers()._handle_group_c_channel(event))


