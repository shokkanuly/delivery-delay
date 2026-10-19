"""Construction Logistics Platform API — one service, three engines.

This module is wiring only: app, middleware, static console, routers.

  Engine 1 · delay prediction   /predict, /predict/batch, /deliveries/{id},
                                /health, /metrics, /train   (api/routers/predict.py)
  Engine 2 · resource scheduler /schedule                   (api/routers/schedule.py)
  Engine 3 · sequence validator /validate                   (api/routers/validate.py)
  Platform                      /projects, /projects/{id}/overview (api/routers/projects.py)
  Evidence loop                 /outcomes, /accuracy, /predictions (api/routers/monitoring.py)
  Business                      /economics, /projects/workspace    (api/routers/business.py)

The trained artifact is loaded once and cached (api/model_store.py). Admin
routes need X-API-Key (api/security.py).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import pathlib
import time


from api.routers import business as business_router
from api.routers import predict as predict_router
from api.routers import projects as projects_router
from api.routers import integrations as integrations_router
from api.routers import monitoring as monitoring_router
from api.routers import schedule as schedule_router
from api.routers import validate as validate_router
from api.security import cors_origins
from db.database import SessionLocal, init_db


def _seed_if_empty() -> None:
    """First boot on a fresh database (a new Railway/Render Postgres, or a
    container with no volume): load the reference data so the three engines
    have something to read. Safe to call on every restart -- it's a no-op
    once `projects` is populated, and it never touches `workspaces` or
    `prediction_log`, so real saved data and the evidence log survive a
    redeploy. Best-effort: a seed failure must not stop the API from serving
    the (fallback-to-CSV) engines, so it's logged, not raised."""
    from db.models import Project
    try:
        with SessionLocal() as db:
            if db.query(Project).count() > 0:
                return
        from db.seed import seed
        print("[startup] empty database — seeding reference data...")
        print("[startup] seeded:", seed())
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] seed skipped ({exc}); engines fall back to bundled CSVs")


@asynccontextmanager
async def lifespan(_app):
    init_db()   # idempotent: creates tables the seed has not (e.g. workspaces)
    _seed_if_empty()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Construction Logistics Platform",
    description="Delay prediction · resource scheduling · sequencing validation",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time-Ms"],
)


@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time-Ms"] = f"{process_time * 1000:.2f}"
    return response

STATIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
@app.get("/console", include_in_schema=False)
def console_view():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Console interface not found")

app.include_router(predict_router.router)
app.include_router(projects_router.router)
app.include_router(business_router.router)
app.include_router(schedule_router.router)
app.include_router(validate_router.router)
app.include_router(monitoring_router.router)
app.include_router(integrations_router.router)
