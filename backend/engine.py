"""
PII detection & redaction engine for government ID documents
(Aadhaar, PAN, Driving License) -- SIH260371.

Pipeline:
  1. YOLO (Ultralytics)  -> object detection: locates the photo/face region
  2. EasyOCR             -> text + bounding box for every text region
  3. Regex + Verhoeff     -> classifies each OCR'd string as a specific PII
     checksum              field (Aadhaar/PAN/DL/DOB/phone/email/address)
                            and validates Aadhaar numbers with the same
                            checksum algorithm UIDAI itself uses

No Presidio, no transformer model -- kept intentionally lean since the
scope is a fixed, well-defined set of Indian ID formats, not open-ended
NLP entity recognition.
"""
import re
from typing import List, Dict, Any

import cv2
from PIL import Image
from ultralytics import YOLO

# ---------------------------------------------------------------------------
# YOLO object detection (photo/face region)
# ---------------------------------------------------------------------------
# COCO-pretrained -- no "face" class, but its "person" class boxes a
# headshot/bust photo on an ID card well. Swap YOLO_WEIGHTS for a
# face-specific checkpoint later if you get one; nothing else changes.
YOLO_WEIGHTS = "yolov8n.pt"
YOLO_PHOTO_CLASS = "person"
YOLO_CONF_THRESHOLD = 0.35

_yolo_model = None
_ocr_reader = None


def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = YOLO(YOLO_WEIGHTS)  # auto-downloads weights on first run
    return _yolo_model


def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False)  # CPU-only
    return _ocr_reader


def _detect_photo_regions(image_path: str) -> List[List[int]]:
    model = get_yolo_model()
    results = model.predict(image_path, conf=YOLO_CONF_THRESHOLD, verbose=False)

    boxes = []
    for result in results:
        names = result.names
        for box in result.boxes:
            if names[int(box.cls[0])] == YOLO_PHOTO_CLASS:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                boxes.append([int(x1), int(y1), int(x2), int(y2)])
    return boxes


# ---------------------------------------------------------------------------
# Verhoeff checksum -- the exact algorithm Aadhaar numbers are checksummed
# with, so a matched string can be confirmed as structurally valid, not
# just "looks like 12 digits."
# ---------------------------------------------------------------------------
_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
]


def verhoeff_is_valid(number_str: str) -> bool:
    """Returns True if `number_str` (digits only) passes the Verhoeff checksum."""
    digits = [int(d) for d in number_str if d.isdigit()]
    if not digits:
        return False
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        checksum = _D[checksum][_P[i % 8][digit]]
    return checksum == 0


# ---------------------------------------------------------------------------
# Regex-based Indian PII field detectors
# ---------------------------------------------------------------------------
AADHAAR_RE = re.compile(r"\b(\d{4}\s?\d{4}\s?\d{4})\b")
PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
DL_RE = re.compile(r"\b([A-Z]{2}[-\s]?\d{2}[-\s]?\d{4,11})\b")
DOB_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
PHONE_RE = re.compile(r"\b([6-9]\d{9})\b")
EMAIL_RE = re.compile(r"\b([\w.+-]+@[\w-]+\.[\w.-]+)\b")
ADDRESS_KEYWORDS = ("address", "s/o", "d/o", "w/o", "street", "road", "village", "district", "pin")
NAME_KEYWORDS = ("name",)


def classify_text(text: str):
    """Returns (class_name, confidence) if `text` matches a known PII field, else None."""
    stripped = text.strip()
    lower = stripped.lower()

    m = AADHAAR_RE.search(stripped)
    if m:
        digits = re.sub(r"\s", "", m.group(1))
        confidence = 0.95 if verhoeff_is_valid(digits) else 0.6
        return "Aadhaar Number", confidence

    if PAN_RE.search(stripped):
        return "PAN Number", 0.9

    if DL_RE.search(stripped):
        return "DL Number", 0.75

    if DOB_RE.search(stripped) and ("dob" in lower or "birth" in lower or DOB_RE.fullmatch(stripped)):
        return "DOB / Date", 0.8

    if PHONE_RE.search(stripped):
        return "Phone Number", 0.85

    if EMAIL_RE.search(stripped):
        return "Email", 0.9

    if any(k in lower for k in ADDRESS_KEYWORDS):
        return "Address", 0.6

    if any(k in lower for k in NAME_KEYWORDS):
        return "Name", 0.55

    return None


def _box_from_ocr(bbox) -> List[int]:
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


def detect_pii(image_path: str):
    """Returns (detections, faces).
    detections: [{class_name, box:[x1,y1,x2,y2], confidence}, ...]
    faces:      [[x1,y1,x2,y2], ...]  (photo regions found by YOLO)
    """
    reader = get_ocr_reader()
    ocr_results = reader.readtext(image_path)  # [(bbox, text, ocr_conf), ...]

    detections = []
    for bbox, text, _ocr_conf in ocr_results:
        if not text or not text.strip():
            continue
        match = classify_text(text)
        if match is None:
            continue
        class_name, confidence = match
        detections.append({
            "class_name": class_name,
            "box": _box_from_ocr(bbox),
            "confidence": round(confidence, 3),
        })

    faces = _detect_photo_regions(image_path)
    return detections, faces


def apply_redaction(image_path: str, detections: List[Dict[str, Any]],
                     faces: List[List[int]], selected_fields: List[str]) -> Image.Image:
    cv_img = cv2.imread(image_path)

    for item in detections:
        if item.get("class_name") in selected_fields:
            x1, y1, x2, y2 = item["box"]
            cv2.rectangle(cv_img, (x1, y1), (x2, y2), (0, 0, 0), -1)

    if "Face (photo)" in selected_fields:
        for (x1, y1, x2, y2) in faces:
            roi = cv_img[y1:y2, x1:x2]
            if roi.size > 0:
                cv_img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (0, 0), sigmaX=15)

    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))