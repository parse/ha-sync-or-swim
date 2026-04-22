import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import analyze, debug, installations, latest, push

app = FastAPI(title="Pahlen Monitor API", version="1.0.0")


@app.on_event("startup")
def save_openapi_json():
    openapi_data = app.openapi()
    # Debug: Print the path being used
    output_path = (
        Path(__file__).resolve().parent.parent.parent / "backend" / "openapi.json"
    )
    print(f"DEBUG: Saving OpenAPI to {output_path}")
    with open(output_path, "w") as f:
        json.dump(openapi_data, f, indent=2)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(push.router, prefix="/push", tags=["push"])
app.include_router(latest.router, prefix="/latest", tags=["latest"])
app.include_router(debug.router, prefix="/debug", tags=["debug"])
app.include_router(
    installations.router, prefix="/installations", tags=["installations"]
)
app.include_router(analyze.router, prefix="/api/analyze", tags=["analyze"])


@app.get("/health")
async def health_check():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
