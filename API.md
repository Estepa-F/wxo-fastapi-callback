# 📡 API Documentation

Complete API reference for the WXO Asynchronous Image Processing service.

---

## Base URL

```
http://localhost:8000
```

---

## Authentication

Currently, no authentication is required. For production deployments, implement appropriate authentication mechanisms (API keys, OAuth, etc.).

---

## Common Headers

All asynchronous endpoints require a callback URL:

```http
callbackUrl: http://your-callback-server/endpoint
```

---

## Endpoints

### 1. Health Check

Check if the service is running.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "ok": true
}
```

**Status Codes:**
- `200 OK` - Service is healthy

---

### 2. COS Configuration

Get current Cloud Object Storage configuration.

**Endpoint:** `GET /cos/config`

**Response:**
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

**Status Codes:**
- `200 OK` - Configuration retrieved successfully

---

### 3. Process Image (Async - Base64 Output)

Process a single image and return the result as base64-encoded data.

**Endpoint:** `POST /process-image-async-b64`

**Headers:**
```http
Content-Type: application/json
callbackUrl: http://your-callback-server/endpoint
```

**Request Body:**
```json
{
  "prompt": "add a dog to the image",
  "filename": "burger.jpeg",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Request Schema:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | Natural language instruction for image modification |
| `filename` | string | No | Original filename (for correlation/tracking) |
| `image_base64` | string | Yes | Base64-encoded image (without `data:` prefix) |

**Immediate Response:**
```json
{
  "accepted": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Status Codes:**
- `202 Accepted` - Job accepted and processing started
- `500 Internal Server Error` - Configuration error (missing API keys, etc.)

**Callback Payload (Success):**
```json
{
  "status": "completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "burger.jpeg",
  "result_image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "result_mime_type": "image/png"
}
```

**Callback Payload (Failure):**
```json
{
  "status": "failed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "burger.jpeg",
  "error": "ValueError: image_base64 invalide (base64 attendu, sans préfixe data:...)"
}
```

---

### 4. Process Image (Async - COS URL Output)

Process a single image and store the result in IBM Cloud Object Storage.

**Endpoint:** `POST /process-image-async`

**Headers:**
```http
Content-Type: application/json
callbackUrl: http://your-callback-server/endpoint
```

**Request Body:**
```json
{
  "prompt": "make the background transparent",
  "filename": "product.png",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Request Schema:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | Natural language instruction for image modification |
| `filename` | string | No | Original filename (for correlation/tracking) |
| `image_base64` | string | Yes | Base64-encoded image (without `data:` prefix) |

**Immediate Response:**
```json
{
  "accepted": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Status Codes:**
- `202 Accepted` - Job accepted and processing started
- `500 Internal Server Error` - Configuration error

**Callback Payload (Success):**
```json
{
  "status": "completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "product.png",
  "object_key": "results/550e8400-e29b-41d4-a716-446655440000/product_modified.png",
  "result_url": "https://s3.eu-de.cloud-object-storage.appdomain.cloud/wxo-images/results/...",
  "expires_in": 900
}
```

**Callback Payload (Failure):**
```json
{
  "status": "failed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "product.png",
  "error": "RuntimeError: COS put_object failed: ClientError: ..."
}
```

---

### 5. Batch Process Images (COS → COS)

Process all images in a COS bucket/prefix with the same instruction.

**Endpoint:** `POST /batch-process-images`

**Headers:**
```http
Content-Type: application/json
callbackUrl: http://your-callback-server/endpoint
```

**Request Body:**
```json
{
  "prompt": "make the image more beautiful"
}
```

**Request Schema:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | Natural language instruction applied to all images |

**Immediate Response:**
```json
{
  "accepted": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Status Codes:**
- `202 Accepted` - Job accepted and processing started
- `500 Internal Server Error` - Configuration error

**Callback Payload (Success):**
```json
{
  "status": "completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_files": 5,
  "processed": 5,
  "failed": 0,
  "fallback_local": 0,
  "duration_seconds": 12.345,
  "total_files_processed": 5,
  "output_bucket": "wxo-images",
  "output_prefix": "results/batch/550e8400-e29b-41d4-a716-446655440000/",
  "errors": []
}
```

**Callback Payload (Partial Success with Fallback):**
```json
{
  "status": "completed_with_errors",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_files": 5,
  "processed": 3,
  "failed": 0,
  "fallback_local": 2,
  "duration_seconds": 15.678,
  "total_files_processed": 5,
  "output_bucket": "wxo-images",
  "output_prefix": "results/batch/550e8400-e29b-41d4-a716-446655440000/",
  "errors": [
    "image1.png: OpenAI billing limit -> fallback local applied",
    "image2.jpg: OpenAI billing limit -> fallback local applied"
  ]
}
```

**Callback Payload (Failure):**
```json
{
  "status": "failed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_files": 0,
  "processed": 0,
  "failed": 0,
  "fallback_local": 0,
  "duration_seconds": 0.123,
  "total_files_processed": 0,
  "output_bucket": "wxo-images",
  "output_prefix": "results/batch/550e8400-e29b-41d4-a716-446655440000/",
  "errors": [],
  "error": "RuntimeError: Missing env var: COS_INPUT_BUCKET"
}
```

**Callback Response Schema:**
| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Job status: `completed`, `completed_with_errors`, or `failed` |
| `job_id` | string | Unique job identifier (UUID) |
| `total_files` | integer | Total number of images found in input bucket |
| `processed` | integer | Images successfully processed via OpenAI |
| `failed` | integer | Images that failed completely (both OpenAI and fallback) |
| `fallback_local` | integer | Images processed via local fallback |
| `duration_seconds` | float | Total processing time in seconds |
| `total_files_processed` | integer | Sum of `processed` + `fallback_local` |
| `output_bucket` | string | COS bucket containing results |
| `output_prefix` | string | Folder path containing processed images |
| `errors` | array | List of error messages (max 20) |
| `error` | string | Fatal error message (only present if status is `failed`) |

---

## Error Handling

### Common Error Responses

**Missing Configuration:**
```json
{
  "detail": "Missing env var: OPENAI_API_KEY"
}
```

**Invalid Base64:**
```json
{
  "status": "failed",
  "job_id": "...",
  "error": "ValueError: image_base64 invalide (base64 attendu, sans préfixe data:...)"
}
```

**OpenAI Billing Limit:**
When OpenAI billing limit is reached, the system automatically falls back to local processing. The callback will include:
```json
{
  "fallback_local": 1,
  "errors": ["image.png: OpenAI billing limit -> fallback local applied"]
}
```

---

## Rate Limiting

Currently, no rate limiting is implemented. For production:
- Implement rate limiting per client/API key
- Consider queue-based processing for batch operations
- Monitor OpenAI API usage and costs

---

## Best Practices

### 1. Callback URL
- Use HTTPS in production
- Implement idempotency (same job_id may be retried)
- Return `200 OK` quickly to acknowledge receipt
- Process callback data asynchronously if needed

### 2. Image Base64 Encoding
```bash
# Correct encoding (no data: prefix)
base64 -i image.jpg | tr -d '\n'

# Incorrect (includes data: prefix)
# Don't use: data:image/jpeg;base64,iVBORw0...
```

### 3. Batch Processing
- Start with small batches to test
- Monitor duration and adjust batch size
- Check `errors` array for partial failures
- Use `fallback_local` count to track OpenAI availability

### 4. Presigned URLs
- URLs expire after `COS_PRESIGN_EXPIRES` seconds (default: 900)
- Download or process results before expiration
- Store object_key for regenerating URLs if needed

---

## Testing with cURL

### Single Image (Base64)
```bash
export B64=$(base64 -i image.jpg | tr -d '\n')

curl -X POST http://localhost:8000/process-image-async-b64 \
  -H "Content-Type: application/json" \
  -H "callbackUrl: http://localhost:9999/callback" \
  -d "{
    \"prompt\": \"add a sunset background\",
    \"filename\": \"image.jpg\",
    \"image_base64\": \"$B64\"
  }"
```

### Batch Processing
```bash
curl -X POST http://localhost:8000/batch-process-images \
  -H "Content-Type: application/json" \
  -H "callbackUrl: http://localhost:9999/callback" \
  -d '{"prompt": "enhance colors and brightness"}'
```

---

## Webhook/Callback Server Example

Simple FastAPI callback server for testing:

```python
from fastapi import FastAPI
import uvicorn
from datetime import datetime, timezone

app = FastAPI()

@app.post("/callback")
def receive_callback(data: dict):
    print(f"\n=== Callback received at {datetime.now(timezone.utc).isoformat()} ===")
    print(f"Status: {data.get('status')}")
    print(f"Job ID: {data.get('job_id')}")
    
    if data.get('status') == 'completed':
        if 'result_image_base64' in data:
            print(f"Result: Base64 image ({len(data['result_image_base64'])} chars)")
        elif 'result_url' in data:
            print(f"Result URL: {data['result_url']}")
        elif 'total_files' in data:
            print(f"Batch: {data['processed']}/{data['total_files']} processed")
    
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9999)
```

---

## OpenAPI/Swagger Documentation

Interactive API documentation is available at:

```
http://localhost:8000/docs
```

Alternative ReDoc documentation:

```
http://localhost:8000/redoc