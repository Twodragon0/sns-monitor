"""
API Backend
REST API 엔드포인트

All routes have been migrated to Blueprint modules under app/api/:
  - /api/dashboard/stats, /api/scans, /api/channels  → app/api/dashboard.py
  - /api/group-*/members, /api/group-*/channel        → app/api/members.py
  - /api/vuddy/creators                               → app/api/vuddy.py
  - /api/dcinside/galleries, /api/dcinside/gallery/*  → app/api/dcinside.py
  - /api/data/*, /api/crawler/results                 → app/api/data.py
  - /api/twitter/search                               → app/api/data.py
  - /api/analyze/url                                  → app/api/analyze.py
  - /api/auth/*                                       → app/api/auth.py
  - /health                                           → app/__init__.py

This file is retained as an empty stub for Lambda compatibility.
"""
