"""Vercel Python Serverless Function entrypoint. Vercel's Python runtime detects the
`app` ASGI object in this module and serves it directly — no WSGI/ASGI adapter needed.
All routing/rewrites are handled by ../vercel.json."""
from app.main import app

__all__ = ["app"]
