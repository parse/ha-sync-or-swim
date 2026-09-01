from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from db.migrations import migrate_shared_sensors_table
from db.session import engine
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from request_timing import elapsed_ms, log_timing
from routes import analyze, debug, installations, latest, ui


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    started = perf_counter()
    migrate_shared_sensors_table(engine)
    log_timing("database_migration", duration_ms=elapsed_ms(started))
    yield


app = FastAPI(title="SyncOrSwim", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def log_sensor_request_timing(request: Request, call_next):  # type: ignore[no-untyped-def]
    if not (
        request.method == "POST"
        and request.url.path.startswith("/api/installations/")
        and request.url.path.endswith("/sensors")
    ):
        return await call_next(request)

    started = perf_counter()
    installation_id = (
        request.url.path.removeprefix("/api/installations/")
        .removesuffix("/sensors")
        .strip("/")
    )
    log_timing(
        "sensor_request_received",
        installation_id=installation_id,
        idempotency_key=request.headers.get("Idempotency-Key", "absent"),
    )
    try:
        response = await call_next(request)
    except BaseException as exc:
        log_timing(
            "sensor_request_failed",
            installation_id=installation_id,
            duration_ms=elapsed_ms(started),
            failure_category=type(exc).__name__,
        )
        raise
    log_timing(
        "sensor_response_generated",
        installation_id=installation_id,
        duration_ms=elapsed_ms(started),
        status_code=response.status_code,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(latest.router, prefix="/latest", tags=["latest"])
app.include_router(latest.router, prefix="/api/latest", tags=["latest"])
app.include_router(debug.router, prefix="/debug", tags=["debug"])
app.include_router(debug.router, prefix="/api/debug", tags=["debug"])


app.include_router(
    installations.router, prefix="/installations", tags=["installations"]
)
app.include_router(
    installations.router, prefix="/api/installations", tags=["installations"]
)
app.include_router(analyze.router, prefix="/api/analyze", tags=["analyze"])
app.include_router(ui.router, prefix="/ui", tags=["ui"])

STATIC_PATH = Path(__file__).with_name("static")
UI_PATH = STATIC_PATH / "ui.html"
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


@app.get("/", include_in_schema=False)
async def web_ui() -> FileResponse:
    return FileResponse(UI_PATH, headers={"Cache-Control": "no-store"})


@app.get("/ui", include_in_schema=False)
async def web_ui_alias() -> FileResponse:
    return FileResponse(UI_PATH, headers={"Cache-Control": "no-store"})


@app.get("/health")
async def health_check() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/health")
async def api_health_check() -> dict[str, bool]:
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
