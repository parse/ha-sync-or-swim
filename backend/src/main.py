from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import analyze, debug, installations, latest

app = FastAPI(title="Pahlen Monitor API", version="1.0.0")


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


@app.get("/health")
async def health_check() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/health")
async def api_health_check() -> dict[str, bool]:
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
