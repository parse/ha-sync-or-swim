from cv_engine import analyze_burst
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()


@router.post("/burst")
async def analyze_image_burst(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        images_bytes = []
        for file in files:
            content = await file.read()
            images_bytes.append(content)

        result = analyze_burst(images_bytes)
        return result
    except Exception as e:
        print(f"Error in analyze_burst: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
