from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import spacy
import fitz
from docx import Document
from PIL import Image
import pytesseract
import io
import base64

# ✅ PDF imports
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

app = FastAPI()

API_KEY = "test123"

# 🔐 USERS (NEW)
users_db = {}

# 📜 HISTORY STORE
history_store = []

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 🔐 LOGIN SYSTEM (NEW)
# =========================
@app.post("/api/register")
def register(data: dict):
    username = data.get("username")
    password = data.get("password")

    if username in users_db:
        return {"error": "User already exists"}

    users_db[username] = password
    return {"message": "User registered"}

@app.post("/api/login")
def login(data: dict):
    username = data.get("username")
    password = data.get("password")

    if users_db.get(username) != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"message": "Login successful", "user": username}

# =========================
# ✅ LIGHTWEIGHT NLP
# =========================
print("🔄 Loading lightweight NLP...")
nlp = spacy.blank("en")
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
# 🤖 SUMMARY
# =========================
def generate_summary(text):
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]
    return ". ".join(sentences[:3])

# =========================
# 🧠 ENTITY + KEYWORDS
# =========================
def extract_entities(text):
    words = text.split()

    stopwords = ["The", "On", "In", "And", "A", "An", "Is", "Are"]

    names = [
        w for w in words
        if w.istitle() and w not in stopwords and len(w) > 2
    ]

    dates = [
        w for w in words
        if any(char.isdigit() for char in w)
    ]

    keywords = list(set([
        w.lower() for w in words
        if len(w) > 6 and w.isalpha()
    ]))[:5]

    return {
        "names": list(set(names[:10])),
        "organizations": [],
        "dates": list(set(dates[:10])),
        "amounts": [],
        "keywords": keywords
    }

# =========================
# 😊 SENTIMENT
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

    summary = generate_summary(text)
    entities = extract_entities(text)
    sentiment = analyze_sentiment(text)

    result = {
        "status": "success",
        "fileName": file_name,
        "text": text,
        "summary": summary,
        "entities": entities,
        "sentiment": sentiment
    }

    # 🔥 SAVE HISTORY
    history_store.append(result)

    return result

# =========================
# 📜 HISTORY API
# =========================
@app.get("/api/history")
def get_history():
    return history_store[::-1]

# =========================
# 📄 PDF API
# =========================
@app.post("/api/download-pdf")
def download_pdf(data: dict, x_api_key: str = Header(None)):

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("📄 AI Document Analysis Report", styles["Title"]))
    content.append(Spacer(1, 20))

    content.append(Paragraph("<b>Summary</b>", styles["Heading2"]))
    content.append(Paragraph(data.get("summary", ""), styles["Normal"]))
    content.append(Spacer(1, 15))

    content.append(Paragraph("<b>Sentiment</b>", styles["Heading2"]))
    content.append(Paragraph(data.get("sentiment", ""), styles["Normal"]))
    content.append(Spacer(1, 15))

    entities = data.get("entities", {})

    content.append(Paragraph("<b>Entities</b>", styles["Heading2"]))
    content.append(Paragraph(f"Names: {', '.join(entities.get('names', []))}", styles["Normal"]))
    content.append(Paragraph(f"Dates: {', '.join(entities.get('dates', []))}", styles["Normal"]))
    content.append(Paragraph(f"Keywords: {', '.join(entities.get('keywords', []))}", styles["Normal"]))

    doc.build(content)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=report.pdf"}
    )