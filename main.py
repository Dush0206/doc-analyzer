from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import spacy, fitz, io, base64
from docx import Document
from PIL import Image
import pytesseract

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

# DATABASE
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# JWT + HASH
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

app = FastAPI()

# ================= JWT =================
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ================= DB =================
engine = create_engine("sqlite:///./app.db")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)

class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True)
    username = Column(String)   # 🔥 IMPORTANT FIX
    fileName = Column(String)
    summary = Column(Text)
    sentiment = Column(String)

Base.metadata.create_all(bind=engine)

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= SECURITY =================
def hash_password(password):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_token(data: dict):
    data["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

# ================= AUTH =================
@app.post("/api/register")
def register(data: dict):
    db = SessionLocal()

    if db.query(User).filter(User.username == data["username"]).first():
        return {"error": "User exists"}

    db.add(User(
        username=data["username"],
        password=hash_password(data["password"])
    ))
    db.commit()

    return {"message": "User registered"}

@app.post("/api/login")
def login(data: dict):
    db = SessionLocal()

    user = db.query(User).filter(User.username == data["username"]).first()

    if not user or not verify_password(data["password"], user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "access_token": create_token({"sub": user.username})
    }

# ================= NLP =================
nlp = spacy.blank("en")

# ================= TEXT EXTRACTION =================
def extract_text(file_bytes, file_type):
    try:
        file_type = file_type.lower()

        if file_type == "pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            return " ".join([p.get_text() for p in doc])

        elif file_type == "docx":
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([p.text for p in doc.paragraphs])

        elif file_type in ["jpg", "jpeg", "png"]:
            img = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(img)

        elif file_type == "txt":
            return file_bytes.decode("utf-8", "ignore")

    except Exception as e:
        print("Error:", e)

    return ""

# ================= AI LOGIC =================
def generate_summary(text):
    return ". ".join([s.strip() for s in text.split(".") if len(s.strip()) > 20][:3])

def extract_entities(text):
    words = text.split()

    return {
        "names": list(set([w for w in words if w.istitle()][:10])),
        "dates": list(set([w for w in words if any(c.isdigit() for c in w)][:10])),
        "keywords": list(set([w.lower() for w in words if len(w) > 6][:5]))
    }

def analyze_sentiment(text):
    t = text.lower()
    if "good" in t: return "POSITIVE"
    if "bad" in t: return "NEGATIVE"
    return "NEUTRAL"

# 🔥 NEW FEATURES
def extract_key_points(text):
    return [s.strip() for s in text.split(".") if len(s.strip()) > 30][:5]

def generate_questions(text):
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 40]
    return ["What is meant by: " + s[:50] + "?" for s in sentences[:3]]

# ================= ROUTES =================
@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/health")
def health():
    return {"status": "running"}

# ================= ANALYZE =================
@app.post("/api/document-analyze")
def analyze(data: dict, authorization: str = Header(None)):

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")

    user = verify_token(authorization.split(" ")[1])
    db = SessionLocal()

    text = extract_text(
        base64.b64decode(data["fileBase64"]),
        data["fileType"]
    )

    summary = generate_summary(text)
    entities = extract_entities(text)
    sentiment = analyze_sentiment(text)
    key_points = extract_key_points(text)
    questions = generate_questions(text)

    # 🔥 USER-BASED HISTORY FIX
    db.add(History(
        username=user,
        fileName=data["fileName"],
        summary=summary,
        sentiment=sentiment
    ))
    db.commit()

    return {
        "user": user,
        "fileName": data["fileName"],
        "text": text,
        "summary": summary,
        "entities": entities,
        "sentiment": sentiment,
        "key_points": key_points,
        "questions": questions
    }

# ================= HISTORY =================
@app.get("/api/history")
def get_history(authorization: str = Header(None)):

    if not authorization:
        raise HTTPException(status_code=401)

    user = verify_token(authorization.split(" ")[1])
    db = SessionLocal()

    records = db.query(History).filter(History.username == user).all()

    return [
        {
            "fileName": r.fileName,
            "summary": r.summary,
            "sentiment": r.sentiment
        }
        for r in records[::-1]
    ]

# ================= PDF =================
@app.post("/api/download-pdf")
def download_pdf(data: dict, authorization: str = Header(None)):

    if not authorization:
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