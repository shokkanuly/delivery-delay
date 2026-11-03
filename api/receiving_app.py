"""Receiving-only deployment: no model loading, analyst UI or synthetic seeding."""
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from api.receiving_boundary import ReceivingBoundary
from api.routers import receiving, receiving_operations
from api.security import cors_origins
from db import database


def create_receiving_app():
    @asynccontextmanager
    async def lifespan(_app):
        if os.getenv('VERCEL') == '1':
            if database.engine.url.get_backend_name() != 'postgresql':
                raise RuntimeError('Vercel receiving requires a persistent PostgreSQL DATABASE_URL; SQLite is not supported.')
            if len(os.getenv('SITEPULSE_ADMIN_KEY', '')) < 32:
                raise RuntimeError('Configure a private SITEPULSE_ADMIN_KEY of at least 32 characters before deploying.')
        database.init_db()
        yield

    app = FastAPI(lifespan=lifespan, title='SitePulse receiving', version='0.3.0',
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_credentials=False,
                       allow_methods=['*'], allow_headers=['*'])
    app.add_middleware(ReceivingBoundary, customer_only=True)
    static = Path(__file__).resolve().parents[1] / 'static'
    app.mount('/static', StaticFiles(directory=static), name='static')

    @app.get('/')
    @app.get('/receive')
    def receiving_view():
        return FileResponse(static / 'receiving.html', headers={
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff'})

    @app.get('/receive-sw.js')
    def service_worker():
        return FileResponse(static / 'receive-sw.js', media_type='application/javascript',
                            headers={'Service-Worker-Allowed': '/', 'Cache-Control': 'no-cache'})

    @app.get('/readyz')
    def readiness():
        with database.SessionLocal() as db:
            db.execute(text('select 1'))
        return {'status': 'ok', 'mode': 'customer', 'receiving': True}

    app.include_router(receiving.router)
    app.include_router(receiving_operations.router)
    return app
