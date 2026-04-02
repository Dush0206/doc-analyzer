from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import spacy
import fitz
from docx import Document
from PIL import Image
import pytesseract
import io
import base64

app = FastAPI()

API_KEY = "test123"

# ✅ Enable CORS (important for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ✅ LOAD MODELS (ONCE)
# =========================
print("🔄 Loading AI models...")

summarizer = pipeline(
    "text2text-generation",
    model="google/flan-t5-small"
)

sentiment_model = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english"
)

nlp = spacy.load("en_core_web_sm")

print("✅ Models loaded successfully!")

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
# 🤖 SUMMARY
# =========================
def generate_summary(text):
    if len(text) < 50:
        return text

    result = summarizer(
        "summarize: " + text[:500],
        max_length=120,
        min_length=30,
        do_sample=False
    )

    return result[0]['generated_text']

# =========================
# 🧠 ENTITY EXTRACTION
# =========================
def extract_entities(text):
    doc = nlp(text)

    names, orgs, dates, money = [], [], [], []

    for ent in doc.ents:
        if ent.label_ == "PERSON":
            names.append(ent.text)
        elif ent.label_ == "ORG":
            orgs.append(ent.text)
        elif ent.label_ == "DATE":
            dates.append(ent.text)
        elif ent.label_ == "MONEY":
            money.append(ent.text)

    return {
        "names": list(set(names)),
        "organizations": list(set(orgs)),
        "dates": list(set(dates)),
        "amounts": list(set(money))
    }

# =========================
# 😊 SENTIMENT
# =========================
def analyze_sentiment(text):
    chunks = [text[i:i+512] for i in range(0, len(text), 512)]
    results = [sentiment_model(chunk)[0]['label'] for chunk in chunks]

    return max(set(results), key=results.count)

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

    # Decode Base64
    try:
        file_bytes = base64.b64decode(file_base64)
    except:
        raise HTTPException(status_code=400, detail="Invalid Base64 data")

    # Extract text
    text = extract_text(file_bytes, file_type)

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text extracted")

    # AI Processing
    summary = generate_summary(text)
    entities = extract_entities(text)
    sentiment = analyze_sentiment(text)

    return {
        "status": "success",
        "fileName": file_name,
        "text": text,
        "summary": summary,
        "entities": entities,
        "sentiment": sentiment
    }