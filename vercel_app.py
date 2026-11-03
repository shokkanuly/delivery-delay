"""Vercel's receiving-only ASGI entrypoint. Configure persistent Postgres first."""
from api.receiving_app import create_receiving_app

app = create_receiving_app()
