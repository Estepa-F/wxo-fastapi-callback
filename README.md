# 📸 WXO – Asynchronous Image Processing with OpenAI & IBM Cloud Object Storage

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-412991.svg)](https://openai.com)
[![IBM Cloud](https://img.shields.io/badge/IBM%20Cloud-Object%20Storage-054ADA.svg)](https://www.ibm.com/cloud/object-storage)

## 📌 Overview

This project implements a set of **asynchronous image processing tools** compatible with **IBM watsonx Orchestrate (WXO)**.

### Key Features

✅ **Single image processing** with AI (OpenAI image editing)  
✅ **Batch image processing** from IBM Cloud Object Storage  
✅ **Asynchronous execution** with callback mechanism  
✅ **Fallback local processing** when OpenAI is unavailable (e.g., billing limit)  
✅ **Structured metrics** for observability and workflows  
✅ **Enterprise-ready** for demos, prototyping, and production workflows

---

## 🧠 Architecture

```
WXO Agent / Workflow
        |
        |  (OpenAPI Tool – async)
        v
FastAPI Tool Server
        |
        |-- OpenAI Image API (primary)
        |-- Local image processing (fallback)
        |
        v
IBM Cloud Object Storage
        |
        v
Callback URL (WXO)
```

### Key Principles

- ⚡ **Non-blocking execution** – All operations are asynchronous
- 🔄 **Single callback per job** – Clean, predictable workflow
- 🎯 **Separation of concerns** – Modular architecture
- 📊 **Observable & debuggable** – Comprehensive metrics and logging

---

## 🧰 Implemented Tools

### 1️⃣ Async Image Processing – Base64 Output

**Endpoint:** `POST /process-image-async-b64`

**Use case:** Modify a single image and return the result directly to the chat or workflow.

**Flow:**
1. User provides an image (base64) and a natural language instruction
2. Image is processed asynchronously via OpenAI
3. Callback returns base64-encoded image + mime type

**Best for:**
- Chat-based interactions
- Visual preview
- Lightweight demos

**Request Example:**
```json
{
  "prompt": "add a dog to the image",
  "filename": "burger.jpeg",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Callback Response:**
```json
{
  "status": "completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "burger.jpeg",
  "result_image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "result_mime_type": "image/png"
}
```

---

### 2️⃣ Async Image Processing – COS URL Output

**Endpoint:** `POST /process-image-async`

**Use case:** Modify a single image and store the result in IBM Cloud Object Storage.

**Flow:**
1. User provides an image (base64) and an instruction
2. Image is processed asynchronously
3. Result is uploaded to COS
4. Callback returns presigned URL + object key

**Best for:**
- Persistent storage
- Sharing & reuse
- Integration with downstream systems

**Request Example:**
```json
{
  "prompt": "make the background transparent",
  "filename": "product.png",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Callback Response:**
```json
{
  "status": "completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "product.png",
  "object_key": "results/550e8400-e29b-41d4-a716-446655440000/product_modified.png",
  "result_url": "https://s3.eu-de.cloud-object-storage.appdomain.cloud/...",
  "expires_in": 900
}
```

---

### 3️⃣ Batch Image Processing – COS → COS

**Endpoint:** `POST /batch-process-images`

**Use case:** Apply the same AI instruction to all images in a COS folder, without selecting files one by one.

**Flow:**
1. User provides a single instruction (prompt)
2. Tool lists all images in input bucket/prefix
3. Processes each image (OpenAI or fallback)
4. Stores results in output bucket/prefix
5. Single callback returns job metrics + processing summary

**Best for:**
- Mass content updates
- E-commerce catalogs
- Marketing assets
- Migration or rebranding use cases

**Request Example:**
```json
{
  "prompt": "make the image more beautiful"
}
```

**Callback Response:**
```json
{
  "status": "completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_files": 3,
  "processed": 3,
  "failed": 0,
  "fallback_local": 3,
  "duration_seconds": 5.7,
  "total_files_processed": 3,
  "output_bucket": "wxo-images",
  "output_prefix": "results/batch/550e8400-e29b-41d4-a716-446655440000/",
  "errors": [
    "Pizza.png: OpenAI billing limit -> fallback local applied"
  ]
}
```

---

## 🚀 Installation & Setup

### Prerequisites

- Python 3.9+
- IBM Cloud Object Storage account
- OpenAI API key

### Installation Steps

1. **Clone the repository:**
```bash
git clone <repository-url>
cd wxo-fastapi-callback
```

2. **Create virtual environment:**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. **Run the server:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug
```

6. **Health check:**
```bash
curl http://127.0.0.1:8000/health
```

Expected response:
```json
{"ok": true}
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# IBM Cloud Object Storage
COS_ENDPOINT=https://s3.eu-de.cloud-object-storage.appdomain.cloud
COS_REGION=eu-de
COS_BUCKET=wxo-images
COS_ACCESS_KEY_ID=your_access_key_here
COS_SECRET_ACCESS_KEY=your_secret_key_here
COS_PRESIGN_EXPIRES=900

# Batch-specific
COS_INPUT_BUCKET=input-images
COS_OUTPUT_BUCKET=wxo-images
COS_INPUT_PREFIX=
COS_OUTPUT_PREFIX=results/batch

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_QUALITY=high
OPENAI_IMAGE_OUTPUT_FORMAT=png
```

### Load Environment Variables

```bash
set -a
source .env
set +a
```

---

## 🧪 Testing

### 1. COS Connectivity Test

```bash
curl http://127.0.0.1:8000/cos/config
```

Expected response:
```json
{
  "endpoint": "https://s3.eu-de.cloud-object-storage.appdomain.cloud",
  "region": "eu-de",
  "input_bucket": "input-images",
  "output_bucket": "wxo-images",
  "input_prefix": "",
  "output_prefix": "results/batch",
  "presign_expires": 900
}
```

### 2. Fake Callback Server (for local testing)

Start a local callback server to receive async responses:

```bash
python - <<'PY'
from fastapi import FastAPI
import uvicorn
from datetime import datetime, timezone

app = FastAPI()

@app.post("/callback")
def cb(data: dict):
    print(f"\n--- {datetime.now(timezone.utc).isoformat()} ---")
    print(data)
    return {"ok": True}

uvicorn.run(app, host="127.0.0.1", port=9999)
PY
```

### 3. Single Image Processing Test (Base64)

```bash
export B64=$(base64 -i burger.jpeg | tr -d '\n')

curl -X POST http://127.0.0.1:8000/process-image-async-b64 \
  -H "Content-Type: application/json" \
  -H "callbackUrl: http://127.0.0.1:9999/callback" \
  -d "{
    \"prompt\": \"add a dog\",
    \"filename\": \"burger.jpeg\",
    \"image_base64\": \"$B64\"
  }"
```

Decode the result:
```bash
python - <<'PY'
import json, base64, sys
data = json.load(sys.stdin)
open("/tmp/out.png","wb").write(base64.b64decode(data["result_image_base64"]))
print("Saved /tmp/out.png")
PY
```

### 4. Batch Processing Test

```bash
curl -X POST http://127.0.0.1:8000/batch-process-images \
  -H "Content-Type: application/json" \
  -H "callbackUrl: http://127.0.0.1:9999/callback" \
  -d '{"prompt":"make the image more beautiful"}'
```

---

## 🧠 Error Handling & Fallback Strategy

### Primary Path
- **OpenAI Image Edit API** is used for all image processing

### Fallback Path
- Triggered on `billing_hard_limit_reached` error
- **Local image processing** is applied:
  - Inverts image colors
  - Adds red watermark text: "DEMO - FALLBACK (OpenAI billing limit)"
- No job failure unless both OpenAI and fallback fail

### Benefits
✅ **Reliable demos** – Always produces output  
✅ **Cost control** – Graceful degradation on billing limits  
✅ **Predictable workflows** – Clear error handling  

---

## 📊 Metrics (Batch Processing)

| Field | Description |
|-------|-------------|
| `total_files` | Images found in input bucket |
| `processed` | Images successfully transformed via OpenAI |
| `failed` | Images that could not be processed at all |
| `fallback_local` | Images processed via local fallback |
| `total_files_processed` | Sum of processed + fallback_local |
| `duration_seconds` | Total batch duration |
| `output_prefix` | Folder containing results |
| `errors` | List of error messages (max 20) |

---

## 🎯 Why This Matters

This setup demonstrates:

✅ **Agentic orchestration** – AI-driven workflows  
✅ **Async tool patterns** – Non-blocking execution  
✅ **Enterprise-ready AI pipelines** – Production-grade architecture  
✅ **Resilience to external API limits** – Fallback mechanisms  
✅ **Clean separation** between UX, AI, and storage  

### Use Cases

- 🎨 **Product demos** – Showcase AI capabilities
- 🏢 **Client workshops** – Hands-on training
- 🚀 **Internal accelerators** – Rapid prototyping
- 📚 **watsonx Orchestrate best practices** – Reference implementation

---

## 📁 Project Structure

```
wxo-fastapi-callback/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not in git)
├── .env.example           # Environment template
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── API.md                 # API documentation
├── ARCHITECTURE.md        # Architecture details
├── burger.jpeg            # Sample image
├── test_processing.py     # Test utilities
├── workspace_config.yaml  # Workspace configuration
└── Main_versions/         # Version history
    ├── main template.py
    ├── main_envoie_cos_tunnel.py
    ├── main_simple_B64_avec_tunnel.py
    ├── main_simple_B64_COS_avec_tunnel.py
    ├── main_simple_B64_COS_OpenAI_avec_tunnel.py
    └── main_simple_B64_sans_tunnel.py
```

---

## 📚 Additional Documentation

- [API Documentation](API.md) - Detailed API reference with all endpoints
- [Architecture](ARCHITECTURE.md) - System design, patterns, and technical decisions

---

## 🔒 Security Notes

- Never commit `.env` file to version control
- Use environment variables for all sensitive credentials
- Rotate API keys regularly
- Use presigned URLs with appropriate expiration times
- Implement proper authentication for production deployments

---

## 📝 License

This project is for demonstration and educational purposes.

---

## 🤝 Contributing

This is a demo project. For questions or suggestions, please contact the maintainer.