from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from db.migrations import migrate_shared_sensors_table
from db.session import engine
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from routes import analyze, debug, installations, latest


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    migrate_shared_sensors_table(engine)
    yield


app = FastAPI(title="SyncOrSwim", version="1.0.0", lifespan=lifespan)


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
@app.get("/installations/sensors/latest-fragment", include_in_schema=False)
async def legacy_fragment_redirect(request: Request) -> RedirectResponse:
    query = request.url.query
    new_url = "/api/installations/sensors/latest-fragment"
    if query:
        new_url += f"?{query}"
    return RedirectResponse(url=new_url, status_code=308)


app.include_router(
    installations.router, prefix="/installations", tags=["installations"]
)
app.include_router(
    installations.router, prefix="/api/installations", tags=["installations"]
)
app.include_router(analyze.router, prefix="/api/analyze", tags=["analyze"])

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
