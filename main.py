from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import spacy
import fitz
from docx import Document
from PIL import Image
import pytesseract
import io
import base64

app = FastAPI()

API_KEY = "test123"

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ✅ LIGHTWEIGHT NLP
# =========================
print("🔄 Loading lightweight NLP...")

nlp = spacy.blank("en")  # ✅ NO heavy model

print("✅ Lightweight NLP loaded!")

# =========================
# 📄 TEXT EXTRACTION
# =========================
def extract_text(file_bytes, file_type):
    file_type = file_type.lower()

    try:
        if file_type == "pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            return " ".join([page.get_text() for page in doc])

        elif file_type == "docx":
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([p.text for p in doc.paragraphs])

        elif file_type in ["jpg", "jpeg", "png", "image"]:
            image = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(image)

        elif file_type == "txt":
            return file_bytes.decode("utf-8", errors="ignore")

    except Exception as e:
        print("❌ Extraction error:", e)

    return ""

# =========================
# 🤖 SIMPLE SUMMARY
# =========================
def generate_summary(text):
    sentences = text.split(".")
    return ".".join(sentences[:3])  # first 3 sentences

# =========================
# 🧠 SIMPLE ENTITY EXTRACTION
# =========================
def extract_entities(text):
    words = text.split()

    names = [w for w in words if w.istitle()]
    dates = [w for w in words if any(char.isdigit() for char in w)]

    return {
        "names": list(set(names[:10])),
        "organizations": [],
        "dates": list(set(dates[:10])),
        "amounts": []
    }

# =========================
# 😊 SIMPLE SENTIMENT
# =========================
def analyze_sentiment(text):
    positive_words = ["good", "great", "excellent", "happy"]
    negative_words = ["bad", "poor", "sad", "worst"]

    text_lower = text.lower()

    pos = sum(word in text_lower for word in positive_words)
    neg = sum(word in text_lower for word in negative_words)

    if pos > neg:
        return "POSITIVE"
    elif neg > pos:
        return "NEGATIVE"
    else:
        return "NEUTRAL"

# =========================
# 🏠 SERVE FRONTEND
# =========================
@app.get("/")
def serve_ui():
    return FileResponse("index.html")

# =========================
# ❤️ HEALTH CHECK
# =========================
@app.get("/health")
def health():
    return {"status": "running"}

# =========================
# 🚀 MAIN API
# =========================
@app.post("/api/document-analyze")
def analyze(data: dict, x_api_key: str = Header(None)):

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    file_name = data.get("fileName")
    file_type = data.get("fileType")
    file_base64 = data.get("fileBase64")

    if not file_name or not file_type or not file_base64:
        raise HTTPException(status_code=400, detail="Missing required fields")

    try:
        file_bytes = base64.b64decode(file_base64)
    except:
        raise HTTPException(status_code=400, detail="Invalid Base64 data")

    text = extract_text(file_bytes, file_type)

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text extracted")

    return {
        "status": "success",
        "fileName": file_name,
        "text": text,
        "summary": generate_summary(text),
        "entities": extract_entities(text),
        "sentiment": analyze_sentiment(text)
    }