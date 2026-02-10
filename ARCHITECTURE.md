# 🏗️ Architecture Documentation

Detailed technical architecture and design decisions for the WXO Asynchronous Image Processing service.

> **📚 Related Documentation:**
> For API contract: [API.md](API.md) · For setup: [README.md](README.md) · For configuration: [CONFIGURATION.md](CONFIGURATION.md)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Patterns](#architecture-patterns)
3. [Component Design](#component-design)
4. [Data Flow](#data-flow)
5. [Error Handling Strategy](#error-handling-strategy)
6. [Scalability Considerations](#scalability-considerations)
7. [Security](#security)
8. [Technical Decisions](#technical-decisions)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WXO Agent / Workflow                      │
│                  (IBM watsonx Orchestrate)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTP POST (OpenAPI Tool)
                         │ + callbackUrl header
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Tool Server                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Endpoints:                                           │  │
│  │  • /process-image-async-b64                          │  │
│  │  • /process-image-async                              │  │
│  │  • /batch-process-images                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                         │                                    │
│         ┌───────────────┴───────────────┐                   │
│         ▼                               ▼                   │
│  ┌─────────────┐              ┌──────────────────┐         │
│  │   OpenAI    │              │ Local Fallback   │         │
│  │ Image Edit  │              │   Processing     │         │
│  │     API     │              │  (PIL/Pillow)    │         │
│  └─────────────┘              └──────────────────┘         │
│         │                               │                   │
│         └───────────────┬───────────────┘                   │
│                         ▼                                    │
│         ┌───────────────────────────────┐                   │
│         │  IBM Cloud Object Storage     │                   │
│         │        (S3 Compatible)        │                   │
│         └───────────────────────────────┘                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTP POST (callback)
                         │ + job results
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Callback Endpoint                         │
│                  (WXO or Custom Server)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture Patterns

### 1. Asynchronous Request-Response Pattern

**Problem:** Image processing can take several seconds, blocking the HTTP connection.

**Solution:** Implement async pattern with callbacks:
1. Accept request immediately (202 Accepted)
2. Process in background
3. Notify via callback when complete

**Benefits:**
- Non-blocking operations
- Better resource utilization
- Scalable to long-running tasks

### 2. Fallback Pattern

**Problem:** External API (OpenAI) may be unavailable or rate-limited.

**Solution:** Implement graceful degradation:
1. Try primary service (OpenAI)
2. On specific errors, fall back to local processing
3. Track fallback usage in metrics

**Benefits:**
- High availability
- Predictable demos
- Cost control

### 3. Single Responsibility Principle

Each component has a clear, focused purpose:
- **Endpoints:** Request validation and job orchestration
- **Background tasks:** Async processing logic
- **Helper functions:** Reusable utilities (COS, OpenAI, naming)
- **Callback handler:** Result delivery

---

## Component Design

### 1. FastAPI Application ([`main.py`](main.py))

**Core Components:**

#### Configuration Management
```python
# Environment-based configuration
COS_ENDPOINT = os.getenv("COS_ENDPOINT", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Validation functions
def _require_cos_config() -> None
def _require_openai_config() -> None
```

**Design Decision:** Use environment variables for all configuration to support:
- 12-factor app principles
- Easy deployment across environments
- Secure credential management

#### Request Models (Pydantic)
```python
class ProcessImageRequest(BaseModel):
    prompt: str
    filename: Optional[str]
    image_base64: str

class BatchProcessRequest(BaseModel):
    prompt: str
```

**Design Decision:** Use Pydantic for:
- Automatic validation
- Type safety
- OpenAPI schema generation

#### Background Task Pattern
```python
@app.post("/process-image-async-b64", status_code=202)
async def process_image_async_b64(
    body: ProcessImageRequest,
    background_tasks: BackgroundTasks,
    callbackUrl: str = Header(...),
):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(process_and_callback_b64, job_id, body, callbackUrl)
    return {"accepted": True, "job_id": job_id}
```

**Design Decision:** Use FastAPI's BackgroundTasks for:
- Simple async execution
- No external queue required
- Suitable for moderate workloads

---

### 2. OpenAI Integration

```python
def edit_image_with_openai(image_bytes: bytes, prompt: str) -> tuple[bytes, str, str]:
    client = OpenAI(api_key=OPENAI_API_KEY)
    result = client.images.edit(
        model=OPENAI_IMAGE_MODEL,
        image=image_file,
        prompt=prompt,
        quality=OPENAI_IMAGE_QUALITY,
        output_format=OPENAI_IMAGE_OUTPUT_FORMAT,
    )
    return out_bytes, mime, output_ext
```

**Design Decisions:**
- Return tuple for multiple outputs (bytes, mime, extension)
- Configurable quality and format via env vars
- Raise exceptions for error handling upstream

---

### 3. Local Fallback Processing

```python
def local_fallback_process(image_bytes: bytes) -> tuple[bytes, str, str]:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = ImageOps.invert(img.convert("RGB")).convert("RGBA")
    
    # Add watermark
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.text((20, 20), "DEMO - FALLBACK (OpenAI billing limit)", fill=(255, 0, 0, 200))
    
    img = Image.alpha_composite(img, overlay)
    return buf.getvalue(), "image/png", "png"
```

**Design Decisions:**
- Simple, visible transformation (invert colors)
- Clear watermark indicating fallback mode
- Always returns PNG for consistency
- No external dependencies beyond Pillow

---

### 4. IBM Cloud Object Storage Integration

```python
def make_s3_client():
    cfg = BotoConfig(
        region_name=COS_REGION,
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        retries={"max_attempts": 3, "mode": "standard"},
    )
    return boto3.client("s3", endpoint_url=COS_ENDPOINT, ...)
```

**Design Decisions:**
- Use boto3 for S3 compatibility
- Path-style addressing for IBM COS
- Automatic retries (3 attempts)
- Presigned URLs for secure, temporary access

---

### 5. Callback Mechanism

```python
async def post_callback(callback_url: str, payload: dict) -> None:
    final_callback_url = rewrite_callback_url(callback_url)
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(final_callback_url, json=payload)
        r.raise_for_status()
```

**Design Decisions:**
- URL rewriting for local development (tunnel support)
- 60-second timeout for callback delivery
- Raise on HTTP errors for visibility
- Single callback per job (no retries in current implementation)

---

## Data Flow

### Single Image Processing (Base64)

```
1. Client → POST /process-image-async-b64
   ├─ Headers: callbackUrl
   └─ Body: {prompt, filename, image_base64}

2. Server → 202 Accepted
   └─ Response: {accepted: true, job_id: "..."}

3. Background Task:
   ├─ Decode base64 → bytes
   ├─ Call OpenAI API
   ├─ Encode result → base64
   └─ POST to callbackUrl
      └─ {status, job_id, result_image_base64, result_mime_type}

4. Client receives callback
```

### Single Image Processing (COS URL)

```
1. Client → POST /process-image-async
   ├─ Headers: callbackUrl
   └─ Body: {prompt, filename, image_base64}

2. Server → 202 Accepted
   └─ Response: {accepted: true, job_id: "..."}

3. Background Task:
   ├─ Decode base64 → bytes
   ├─ Call OpenAI API
   ├─ Upload to COS
   ├─ Generate presigned URL
   └─ POST to callbackUrl
      └─ {status, job_id, object_key, result_url, expires_in}

4. Client receives callback
```

### Batch Processing

```
1. Client → POST /batch-process-images
   ├─ Headers: callbackUrl
   └─ Body: {prompt}

2. Server → 202 Accepted
   └─ Response: {accepted: true, job_id: "..."}

3. Background Task:
   ├─ List all objects in COS_INPUT_BUCKET
   ├─ For each image:
   │  ├─ Download from COS
   │  ├─ Try OpenAI API
   │  │  └─ On billing_hard_limit_reached:
   │  │     └─ Fall back to local processing
   │  └─ Upload result to COS_OUTPUT_BUCKET
   ├─ Collect metrics (processed, failed, fallback_local)
   └─ POST to callbackUrl (single callback)
      └─ {status, job_id, total_files, processed, failed, 
          fallback_local, duration_seconds, output_prefix, errors}

4. Client receives callback with complete batch results
```

---

## Error Handling Strategy

### 1. Configuration Errors (Fail Fast)

```python
def _require_cos_config() -> None:
    missing = []
    if not COS_ENDPOINT: missing.append("COS_ENDPOINT")
    # ...
    if missing:
        raise RuntimeError(f"Missing COS env vars: {', '.join(missing)}")
```

**Strategy:** Validate configuration at endpoint entry, return 500 immediately.

### 2. Processing Errors (Graceful Degradation)

```python
try:
    out_bytes, out_mime, out_ext = edit_image_with_openai(img_bytes, req.prompt)
except Exception as e:
    if "billing_hard_limit_reached" in str(e):
        # Fallback to local processing
        out_bytes, out_mime, out_ext = local_fallback_process(img_bytes)
        fallback_local += 1
    else:
        # Record failure
        failed += 1
        errors.append(f"{k}: {msg}")
```

**Strategy:** 
- Specific error detection (billing limit)
- Automatic fallback
- Track metrics for observability

### 3. Callback Errors (Log and Continue)

```python
try:
    await post_callback(callback_url, payload)
except Exception as cb_err:
    print("!!! CALLBACK FAILED !!!", repr(cb_err))
```

**Strategy:** Log callback failures but don't crash the service.

**Future Enhancement:** Implement retry queue for failed callbacks.

---

## Scalability Considerations

### Current Implementation (Single Server)

**Suitable for:**
- Demos and prototypes
- Low to moderate traffic (< 100 concurrent jobs)
- Development and testing

**Limitations:**
- Background tasks run in-process
- No job persistence
- Server restart loses in-flight jobs

### Production Scaling Options

#### Option 1: Horizontal Scaling + Queue

```
Load Balancer
    ├─ FastAPI Server 1 ─┐
    ├─ FastAPI Server 2 ─┼─→ Redis/RabbitMQ ─→ Worker Pool
    └─ FastAPI Server N ─┘
```

**Changes Required:**
- Replace BackgroundTasks with Celery/RQ
- Add Redis for job queue
- Implement job persistence
- Add worker auto-scaling

#### Option 2: Serverless

```
API Gateway → Lambda/Cloud Functions → S3/COS
                  ↓
            Step Functions (orchestration)
```

**Changes Required:**
- Refactor to stateless functions
- Use cloud-native orchestration
- Implement callback via SNS/EventBridge

---

## Security

### Current Implementation

**Strengths:**
- No credentials in code
- Environment-based configuration
- Presigned URLs with expiration

**Gaps (for production):**
- No authentication on endpoints
- No rate limiting
- No input sanitization beyond Pydantic validation

### Production Recommendations

1. **Authentication:**
   - API keys via headers
   - OAuth 2.0 for enterprise
   - JWT tokens for user context

2. **Authorization:**
   - Role-based access control
   - Bucket-level permissions
   - Quota management per client

3. **Input Validation:**
   - Image size limits
   - Prompt content filtering
   - File type validation

4. **Network Security:**
   - HTTPS only
   - CORS configuration
   - IP whitelisting for callbacks

5. **Secrets Management:**
   - Use AWS Secrets Manager / IBM Key Protect
   - Rotate credentials regularly
   - Audit access logs

---

## Technical Decisions

### Why FastAPI?

**Pros:**
- Native async support
- Automatic OpenAPI documentation
- Type hints and validation
- High performance (Starlette + Pydantic)

**Alternatives Considered:**
- Flask: Lacks native async
- Django: Too heavy for microservice
- Express.js: Would require Node.js ecosystem

### Why Boto3 for COS?

**Pros:**
- S3-compatible API
- Mature, well-documented
- Presigned URL support
- Automatic retries

**Alternatives Considered:**
- ibm-cos-sdk: Less maintained
- Direct HTTP: More complex

### Why Pillow for Fallback?

**Pros:**
- Pure Python (easy deployment)
- Rich image manipulation
- No external dependencies
- Fast for simple operations

**Alternatives Considered:**
- OpenCV: Overkill for simple transforms
- ImageMagick: External binary dependency

### Why Single Callback?

**Pros:**
- Simple integration
- Predictable workflow
- Easy debugging

**Cons:**
- No progress updates
- No retry mechanism

**Future Enhancement:** Add optional progress callbacks for batch operations.

---

## Monitoring and Observability

### Current Logging

```python
print("=== CALLBACK ===")
print("original :", callback_url)
print("rewritten:", final_callback_url)
```

**Limitations:** Console-only, no structured logging.

### Production Recommendations

1. **Structured Logging:**
```python
import structlog

logger = structlog.get_logger()
logger.info("callback_sent", 
    job_id=job_id, 
    callback_url=callback_url,
    status=status)
```

2. **Metrics:**
   - Job duration histogram
   - Success/failure rates
   - Fallback usage percentage
   - OpenAI API latency

3. **Tracing:**
   - OpenTelemetry integration
   - Distributed tracing across services
   - Correlation IDs

4. **Alerting:**
   - High failure rate
   - Callback delivery failures
   - OpenAI API errors

---

## Future Enhancements

### Short Term
- [ ] Add retry logic for callbacks
- [ ] Implement request ID tracking
- [ ] Add health check for OpenAI API
- [ ] Support more image formats

### Medium Term
- [ ] Add job status query endpoint
- [ ] Implement webhook signature verification
- [ ] Add batch job cancellation
- [ ] Support video processing

### Long Term
- [ ] Multi-model support (Stable Diffusion, DALL-E)
- [ ] Custom model fine-tuning
- [ ] Real-time progress streaming
- [ ] Advanced image analysis (OCR, object detection)

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [IBM Cloud Object Storage](https://cloud.ibm.com/docs/cloud-object-storage)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Pillow Documentation](https://pillow.readthedocs.io/)