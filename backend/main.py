"""
FastAPI backend for PII Shield.
Matches the React frontend's expected API exactly:
  POST /detect  (file)                                   -> {detections, faces}
  POST /redact  (file, detections, faces, selected_fields) -> redacted image (JPEG)

Run:
  uvicorn main:app --reload --port 8000
"""
import io
import json
import os
import tempfile

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from engine import detect_pii, apply_redaction

app = FastAPI(title="PII Shield API")

# React dev servers: CRA default (3000) and Vite default (5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _save_upload(file: UploadFile) -> str:
    suffix = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.file.read())
        return tmp.name


@app.post("/detect")
async def detect(file: UploadFile = File(...)):
    temp_path = _save_upload(file)
    try:
        detections, faces = detect_pii(temp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.remove(temp_path)
    return {"detections": detections, "faces": faces}


@app.post("/redact")
async def redact(
    file: UploadFile = File(...),
    detections: str = Form(...),
    faces: str = Form(...),
    selected_fields: str = Form(...),
):
    temp_path = _save_upload(file)
    try:
        result_image = apply_redaction(
            temp_path,
            json.loads(detections),
            json.loads(faces),
            json.loads(selected_fields),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.remove(temp_path)

    buf = io.BytesIO()
    result_image.save(buf, format="JPEG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")


@app.get("/health")
async def health():
    return {"status": "ok"}