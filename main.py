from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import fitz
from docx import Document
from PIL import Image
import pytesseract
import io
import base64

app = FastAPI()

# 🔐 API KEY (REQUIRED)
API_KEY = "sk_track2_987654321"

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return ". ".join(sentences[:3]) if sentences else "No summary available"

def extract_entities(text):
    words = text.split()

    names = [w for w in words if w.istitle()]
    dates = [w for w in words if any(c.isdigit() for c in w)]
    keywords = [w.lower() for w in words if len(w) > 6][:5]

    return {
        "names": list(set(names[:10])),
        "dates": list(set(dates[:10])),
        "organizations": [],
        "amounts": [],
        "keywords": list(set(keywords))
    }

def analyze_sentiment(text):
    text = text.lower()
    if "good" in text:
        return "Positive"
    elif "bad" in text:
        return "Negative"
    return "Neutral"

# =========================
# 🏠 HOME
# =========================
@app.get("/")
def home():
    return FileResponse("index.html")

# =========================
# 🚀 MAIN API (IMPORTANT)
# =========================
@app.post("/api/document-analyze")
def analyze(data: dict, x_api_key: str = Header(None)):

    # 🔐 API KEY CHECK
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    file_bytes = base64.b64decode(data["fileBase64"])
    text = extract_text(file_bytes, data["fileType"])

    summary = generate_summary(text)
    entities = extract_entities(text)
    sentiment = analyze_sentiment(text)

    return {
        "status": "success",
        "fileName": data["fileName"],
        "summary": summary,
        "entities": entities,
        "sentiment": sentiment
    }