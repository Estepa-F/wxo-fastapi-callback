# 📸 WXO – Asynchronous Image Processing with OpenAI & IBM Cloud Object Storage

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-412991.svg)](https://openai.com)
[![IBM Cloud](https://img.shields.io/badge/IBM%20Cloud-Object%20Storage-054ADA.svg)](https://www.ibm.com/cloud/object-storage)

> **📚 Related Documentation:**
> [API.md](API.md) · [CONFIGURATION.md](CONFIGURATION.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [tools Orchestrate/README.md](tools%20Orchestrate/README.md)

> **🧭 Where to start?**
> - Want to run it locally? → You're in the right place (README.md)
> - Want to configure it? → [CONFIGURATION.md](CONFIGURATION.md)
> - Want to integrate via API? → [API.md](API.md)
> - Want to understand design choices? → [ARCHITECTURE.md](ARCHITECTURE.md)
> - Want to use it in WXO? → [tools Orchestrate/README.md](tools%20Orchestrate/README.md)

---

## 📌 Overview

Asynchronous image processing tools for **IBM watsonx Orchestrate (WXO)** with AI-powered transformations via OpenAI and persistent storage in IBM Cloud Object Storage.

> **💡 Design Philosophy:**
> This project is **production-ready by design** (async patterns, error handling, observability), but intentionally simplified (in-process background tasks) for **demo and enablement purposes**. See [ARCHITECTURE.md](ARCHITECTURE.md) for production scaling options.

### Key Features

✅ **Single image processing** with AI (OpenAI image editing)
✅ **Batch image processing** from IBM Cloud Object Storage
✅ **Asynchronous execution** with callback mechanism
✅ **Fallback local processing** when OpenAI is unavailable
✅ **Enterprise-ready** for demos, prototyping, and production workflows

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (3.9+ supported, 3.10+ recommended)
- **IBM Cloud Object Storage** account with HMAC credentials
- **OpenAI API key** from https://platform.openai.com/api-keys
- **For local development on Mac**: Lima VM with watsonX Orchestrate ADK

### Installation

1. **Clone and setup:**
```bash
git clone https://github.com/Estepa-F/wxo-fastapi-callback.git
cd wxo-fastapi-callback
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your credentials (see CONFIGURATION.md for details)
```

3. **Load environment variables:**

> ⚠️ **CRITICAL**: You MUST load `.env` before running the server!

```bash
set -a
source .env
set +a
```

**Verify variables are loaded:**
```bash
echo $COS_ENDPOINT
# Should print: https://s3.eu-de.cloud-object-storage.appdomain.cloud

echo $OPENAI_API_KEY | wc -c
# Should print a number > 10 (without exposing the key)
```

4. **Run the server:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug
```

> ⚠️ **Important**: Use `--host 0.0.0.0` (not `127.0.0.1`) to make the server accessible from Lima VM.
>
> **Troubleshooting**: If `curl http://host.lima.internal:8000/health` fails from inside the VM, it's almost always because FastAPI was started with `127.0.0.1` instead of `0.0.0.0`.

5. **Verify it's running:**
```bash
curl http://localhost:8000/health
# Expected: {"ok": true}
```

---

## 🧪 Quick Test

### Option 1: Automated Test Script (Recommended)

The easiest way to verify your setup:

```bash
# 1. Make the script executable
chmod +x scripts/test_local.sh

# 2. Load environment variables
set -a
source .env
set +a

# 3. Start FastAPI (in a separate terminal)
uvicorn main:app --host 0.0.0.0 --port 8000

# 4. Run the test script
./scripts/test_local.sh
```

**What it does:**
- ✅ Verifies all required environment variables
- ✅ Checks FastAPI server health
- ✅ Validates COS configuration
- ✅ Starts a local callback server automatically
- ✅ Tests single image processing (Base64)
- ✅ Tests batch image processing
- ✅ Cleans up resources on exit

**Prerequisites:**
- Test image `burger.jpeg` in project root (for single image test)
- Input bucket with test images (for batch test)

---

### Option 2: Manual Testing

#### Prerequisites for Batch Processing

Before testing batch operations, ensure:

✅ **Input bucket exists** and contains test images (JPEG, PNG)
✅ **Output bucket exists** (can be the same as input)
✅ **HMAC credentials have permissions**: `list`, `get`, `put`
✅ **Configuration is valid**:
```bash
curl http://localhost:8000/cos/config
# Verify: endpoint, input_bucket, output_bucket match your setup
```

#### 1. Start a Callback Server

In a new terminal:
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

#### 2. Process an Image

```bash
export B64=$(base64 -i your-image.jpg | tr -d '\n')

curl -X POST http://localhost:8000/process-image-async-b64 \
  -H "Content-Type: application/json" \
  -H "callbackUrl: http://localhost:9999/callback" \
  -d "{
    \"prompt\": \"add a sunset background\",
    \"filename\": \"test.jpg\",
    \"image_base64\": \"$B64\"
  }"
```

You should see:
1. Immediate response: `{"accepted": true, "job_id": "..."}`
2. Callback in terminal 1 with the processed image (base64)

---

## 🖥️ Local Development with watsonX Orchestrate (Mac + Lima VM)

### Architecture

```
Mac (Host)
├── FastAPI Server (port 8000)
│   └── http://0.0.0.0:8000
│
└── Lima VM (ibm-watsonx-orchestrate)
    ├── watsonX Orchestrate ADK (port 4321)
    │   └── Accessible via SSH tunnel: localhost:14321
    │
    └── Access to Mac host via: host.lima.internal:8000
```

### Why `host.lima.internal:8000`?

Lima VM uses an isolated network. The special DNS alias **`host.lima.internal`** resolves to the Mac host's IP from within the VM, allowing Orchestrate to communicate with your FastAPI server.

### Setup Steps

**1. Start FastAPI on Mac:**
```bash
cd wxo-fastapi-callback
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug
```

**2. Start Lima VM:**
```bash
limactl start ibm-watsonx-orchestrate
```

**3. Create SSH Tunnel:**
```bash
ssh -o 'IdentityFile="/Users/YOUR_USERNAME/.lima/_config/user"' \
  -o StrictHostKeyChecking=no \
  -o Hostname=127.0.0.1 \
  -o Port=YOUR_LIMA_SSH_PORT \
  -N \
  -L 14321:127.0.0.1:4321 \
  lima-ibm-watsonx-orchestrate
```

> 📝 Replace `YOUR_USERNAME` and `YOUR_LIMA_SSH_PORT` (check with `limactl list`)

**4. Access Orchestrate:**
```
http://localhost:14321
```

**5. Test Connectivity:**
```bash
limactl shell ibm-watsonx-orchestrate
curl http://host.lima.internal:8000/health
# Expected: {"ok": true}
```

**6. Import Tools:**

Import these files from `tools Orchestrate/` into watsonX Orchestrate:
- YAML files as API tools
- Python file as Python tool  
- JSON files as workflows

See [tools Orchestrate/README.md](tools%20Orchestrate/README.md) for detailed instructions.

---

## ⚠️ Known Pitfalls

- **`callbackUrl` header is case-sensitive** - Use exactly `callbackUrl`, not `callbackurl` or `callback_url`
- **No `data:` prefix in Base64** - Send raw Base64 string without `data:image/...;base64,` prefix
- **Use `--host 0.0.0.0`** - Required for Lima VM access, `127.0.0.1` won't work
- **Source `.env` before running** - Run `set -a && source .env && set +a` or server will fail
- **COS buckets must exist** - Create input/output buckets in IBM Cloud before testing batch

---

## 🧰 Available Tools

### 1️⃣ Single Image (Base64 Output)
**Endpoint:** `POST /process-image-async-b64`  
**Use case:** Process one image, return result directly in chat/workflow  
**Best for:** Quick demos, visual preview, lightweight interactions

### 2️⃣ Single Image (COS URL Output)
**Endpoint:** `POST /process-image-async`  
**Use case:** Process one image, store in COS, return presigned URL  
**Best for:** Persistent storage, sharing, integration with other systems

### 3️⃣ Batch Processing (COS → COS)
**Endpoint:** `POST /batch-process-images`  
**Use case:** Apply same instruction to all images in a COS folder  
**Best for:** Mass content updates, e-commerce catalogs, marketing assets

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **[API.md](API.md)** | Complete API reference with endpoints, schemas, and examples |
| **[CONFIGURATION.md](CONFIGURATION.md)** | Environment variables and setup guide |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Technical architecture, patterns, and design decisions |
| **[tools Orchestrate/README.md](tools%20Orchestrate/README.md)** | watsonX Orchestrate integration guide |

---

## 🎯 Use Cases

- 🎨 **Product demos** – Showcase AI capabilities
- 🏢 **Client workshops** – Hands-on training
- 🚀 **Internal accelerators** – Rapid prototyping
- 📚 **watsonx Orchestrate best practices** – Reference implementation

---

## 🔒 Security Notes

- Never commit `.env` to version control
- Use environment variables for all credentials
- Rotate API keys regularly
- Use presigned URLs with appropriate expiration
- See [CONFIGURATION.md](CONFIGURATION.md) for production security recommendations

---

## 🤝 Contributing

This is a demo project for IBM watsonx Orchestrate. For questions or suggestions, please contact the maintainer.

---

## 📝 License

This project is for demonstration and educational purposes.