# PII Shield — Automated PII Detection & Redaction for Government ID Documents

## What it does

1. Upload a photo/scan of an Aadhaar, PAN, or Driving License.
2. The system detects:
   - The **photo/face region** (object detection)
   - **Text-based PII fields**: Aadhaar number, PAN number, DL number, DOB,
     phone number, email, address, name
3. Review the detected fields — each is a toggle-able checkbox.
4. Apply redaction — selected text fields get blacked out, the face gets
   blurred.
5. Download the redacted document.

## Architecture

```
┌─────────────┐   image upload   ┌───────────────────┐
│   React     │ ───────────────▶ │   FastAPI backend   │
│  frontend   │                  │                     │
│  (Vite)     │ ◀─────────────── │  POST /detect       │
└─────────────┘   detections     │  POST /redact       │
                                  └──────────┬──────────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     ▼                       ▼                       ▼
             ┌───────────────┐      ┌───────────────┐      ┌──────────────────┐
             │  YOLO          │      │  EasyOCR       │      │  Regex +         │
             │  (Ultralytics) │      │  (text + box   │      │  Verhoeff        │
             │  → photo/face  │      │   per region)  │      │  checksum        │
             │  region        │      │                │      │  → classifies    │
             │  (object       │      │                │      │  each string as  │
             │  detection)    │      │                │      │  a PII field     │
             └───────────────┘      └───────────────┘      └──────────────────┘
```

No Presidio, no transformer model — the field classification is deliberately
lean regex + a real checksum algorithm (Verhoeff, the same one UIDAI uses
for Aadhaar), since the scope is a fixed set of Indian ID formats rather than
open-ended NLP entity recognition.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) |
| Backend | FastAPI |
| Object detection | YOLOv8 (Ultralytics) |
| OCR | EasyOCR |
| PII classification | Regex + Verhoeff checksum (Aadhaar) |
| Package management | uv (backend), npm (frontend) |

## Project structure

```
SIH Image detection/
├── backend/
│   ├── main.py            # FastAPI app: /detect, /redact, /health
│   ├── engine.py           # YOLO + OCR + regex/checksum pipeline
│   ├── pyproject.toml      # uv project config + dependencies
│   ├── uv.lock
│   └── .python-version
├── frontend/
│   ├── src/                # React app (App.jsx etc.)
│   ├── package.json
│   └── vite.config.js
└── .gitignore
```

## Setup

### Backend

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

Runs at `http://127.0.0.1:8000`. CPU-only — no GPU required.
`yolov8n.pt` weights auto-download (a few MB) on the first `/detect` call.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Usage

1. Start the backend, then the frontend (separate terminals).
2. Open the frontend in your browser.
3. Upload an ID document image.
4. Click **Detect PII** — detected fields appear as checkboxes.
5. Choose which fields to redact (all are pre-selected by default).
6. Click **Apply Redaction**, then **Download Redacted Document**.

## Known limitations

- Driving License number regex is a simplified approximation — real DL
  formats vary by issuing state.
- Name and address detection are keyword-heuristic, not true NLP, so they're
  less reliable than the ID-number fields.
- The photo/face region uses YOLO's generic `person` class (COCO-pretrained,
  no dedicated "face" class) — works well for ID photos but isn't a
  face-specific detector. Swappable for a face-trained checkpoint later.
- First request after starting the backend is slow (models loading into
  memory); subsequent requests are fast.

## Roadmap

- Fine-tuned/face-specific YOLO checkpoint for tighter photo detection
- Broader document type support (Voter ID, MHA-issued ID cards)
- Batch document processing
- Audit log / consent tracking for organizational use
