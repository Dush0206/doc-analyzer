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

# ✅ PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

# ✅ DATABASE
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

app = FastAPI()

API_KEY = "test123"

# =========================
# 💾 DATABASE SETUP
# =========================
DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =========================
# 🧱 TABLES
# =========================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)

class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True)
    fileName = Column(String)
    summary = Column(Text)
    sentiment = Column(String)

Base.metadata.create_all(bind=engine)

# =========================
# ✅ CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 🔐 AUTH
# =========================
@app.post("/api/register")
def register(data: dict):
    db = SessionLocal()

    user = db.query(User).filter(User.username == data["username"]).first()
    if user:
        return {"error": "User exists"}

    new_user = User(username=data["username"], password=data["password"])
    db.add(new_user)
    db.commit()

    return {"message": "User registered"}

@app.post("/api/login")
def login(data: dict):
    db = SessionLocal()

    user = db.query(User).filter(
        User.username == data["username"],
        User.password == data["password"]
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"message": "Login successful", "user": user.username}

# =========================
# NLP
# =========================
nlp = spacy.blank("en")

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

        elif file_type in ["jpg", "jpeg", "png"]:
            image = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(image)

        elif file_type == "txt":
            return file_bytes.decode("utf-8", errors="ignore")

    except:
        return ""

    return ""

# =========================
# 🤖 AI LOGIC
# =========================
def generate_summary(text):
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]
    return ". ".join(sentences[:3])

def extract_entities(text):
    words = text.split()

    names = [w for w in words if w.istitle() and len(w) > 2]
    dates = [w for w in words if any(c.isdigit() for c in w)]
    keywords = [w.lower() for w in words if len(w) > 6][:5]

    return {
        "names": list(set(names[:10])),
        "organizations": [],
        "dates": list(set(dates[:10])),
        "amounts": [],
        "keywords": list(set(keywords))
    }

def analyze_sentiment(text):
    if "good" in text.lower():
        return "POSITIVE"
    elif "bad" in text.lower():
        return "NEGATIVE"
    return "NEUTRAL"

# =========================
# ROUTES
# =========================
@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/health")
def health():
    return {"status": "running"}

# =========================
# 🚀 ANALYZE
# =========================
@app.post("/api/document-analyze")
def analyze(data: dict, x_api_key: str = Header(None)):

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    db = SessionLocal()

    file_bytes = base64.b64decode(data["fileBase64"])
    text = extract_text(file_bytes, data["fileType"])

    summary = generate_summary(text)
    entities = extract_entities(text)
    sentiment = analyze_sentiment(text)

    # 💾 SAVE TO DB
    new_history = History(
        fileName=data["fileName"],
        summary=summary,
        sentiment=sentiment
    )

    db.add(new_history)
    db.commit()

    return {
        "fileName": data["fileName"],
        "text": text,
        "summary": summary,
        "entities": entities,
        "sentiment": sentiment
    }

# =========================
# 📜 HISTORY FROM DB
# =========================
@app.get("/api/history")
def get_history():
    db = SessionLocal()
    records = db.query(History).all()

    return [
        {
            "fileName": r.fileName,
            "summary": r.summary,
            "sentiment": r.sentiment
        }
        for r in records[::-1]
    ]

# =========================
# 📄 PDF
# =========================
@app.post("/api/download-pdf")
def download_pdf(data: dict, x_api_key: str = Header(None)):

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    content = [
        Paragraph("📄 AI Report", styles["Title"]),
        Spacer(1, 20),
        Paragraph(data.get("summary", ""), styles["Normal"]),
        Spacer(1, 10),
        Paragraph(data.get("sentiment", ""), styles["Normal"]),
    ]

    doc.build(content)
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf")