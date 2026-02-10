# 📡 API Documentation

Complete API reference for the WXO Asynchronous Image Processing service.

---

## Base URLs

**Local Development:**
```
http://localhost:8000
```

**Lima VM (from watsonX Orchestrate):**
```
http://host.lima.internal:8000
```

> See [README.md](README.md#local-development-with-watsonx-orchestrate-mac--lima-vm) for Lima VM setup details.

---

## Configuration

All configuration is managed via environment variables. See [CONFIGURATION.md](CONFIGURATION.md) for complete setup guide.

**Quick validation:**
```bash
curl http://localhost:8000/cos/config
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

## Concepts and Metrics Definitions

Understanding the key metrics returned by the batch processing endpoint:

### Core Metrics

**`total_files`**
Total number of image files discovered in the input bucket/prefix. This represents all images found before processing begins.

**`processed`**
Number of images successfully processed using the OpenAI API. These images were transformed according to the provided prompt using OpenAI's image editing capabilities.

**`fallback_local`**
Number of images processed using the local fallback mechanism. This occurs when OpenAI is unavailable or returns a billing error. The fallback applies a simple transformation (color inversion + watermark) to ensure the workflow completes successfully.

**`failed`**
Number of images that failed both OpenAI and fallback processing. These images could not be processed at all due to errors (e.g., corrupted files, unsupported formats, upload failures).

**`total_files_processed`**
Total number of images that produced an output image. This value equals `processed + fallback_local` and represents the actual number of results available in the output bucket.

### Status Values

**`completed`**
All images were processed successfully via OpenAI. No fallback was needed, and no failures occurred.

**`completed_with_errors`**
The batch job completed, but some images used fallback processing or encountered non-fatal errors. Check the `errors` array for details. All images still produced output.

**`failed`**
The batch job failed completely. This typically indicates a configuration error (missing credentials, invalid bucket names) or a critical system error. Check the `error` field for the root cause.

### Duration and Performance

**`duration_seconds`**
Total time taken to process the entire batch, measured in seconds. This includes:
- Listing files in the input bucket
- Processing each image (OpenAI API calls or fallback)
- Uploading results to the output bucket
- Generating the callback payload

Use this metric to estimate processing time for future batches and optimize batch sizes.

---

## watsonx Orchestrate (WXO) Integration Notes

### OpenAPI Tool Configuration

Each endpoint is exposed as an **OpenAPI Tool** in watsonX Orchestrate. The tool definitions are provided in the `tools Orchestrate/` directory:

- `Async_Image_Processing_B64.yaml` - Single image with Base64 output
- `Async_Image_Processing_COS.yaml` - Single image with COS URL output
- `Async_Image_Batch_Process_COS.yaml` - Batch processing

### Callback Requirements

**Header Name**
The callback URL header name is **case-sensitive** and must be exactly `callbackUrl` (camelCase). Using `callbackurl`, `CallbackUrl`, or any other variation will cause the tool to fail.

```http
callbackUrl: http://your-orchestrate-instance/callback-endpoint
```

**Callback Schema**
WXO expects the callback payload to **strictly match** the OpenAPI callback schema defined in the YAML files. Any deviation (missing fields, wrong types, extra fields) may cause workflow failures.

**Response Time**
The callback endpoint must respond quickly with **HTTP 200 OK**. WXO has timeout limits for callback responses. If your callback handler needs to perform heavy processing, acknowledge receipt immediately and process asynchronously.

```python
@app.post("/callback")
async def handle_callback(data: dict):
    # Acknowledge immediately
    asyncio.create_task(process_callback_async(data))
    return {"ok": True}  # Return 200 OK quickly
```

### Asynchronous Tool Pattern

All endpoints follow the **async tool pattern**:

1. **Immediate Response (202 Accepted)**
   Returns `job_id` immediately, allowing the workflow to continue without blocking.

2. **Background Processing**
   The actual work happens asynchronously in a background task.

3. **Callback Notification**
   When processing completes, a POST request is sent to the `callbackUrl` with the results.

This pattern is essential for long-running operations and prevents workflow timeouts.

### Local Development with Lima VM

When testing locally on Mac with watsonX Orchestrate ADK installed via Lima VM, use the special hostname:

```yaml
servers:
  - url: http://host.lima.internal:8000
```

This allows the VM to communicate with the FastAPI server running on the Mac host. See the main [README.md](README.md) for detailed setup instructions.

### Best Practices for WXO Integration

✅ **Always define callback schemas** in your OpenAPI spec
✅ **Use exact header names** (`callbackUrl`, not `callback_url`)
✅ **Return 202 Accepted** for async operations
✅ **Keep callback responses fast** (< 5 seconds)
✅ **Include job_id** in all responses for correlation
✅ **Test with local callback server** before deploying to WXO
✅ **Handle retries gracefully** (callbacks may be sent multiple times)

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

## cURL Examples

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

## Best Practices

### Callback URLs
- Use HTTPS in production
- Implement idempotency (same job_id may be retried)
- Return `200 OK` quickly (< 5 seconds)
- Process callback data asynchronously if needed

### Image Encoding
```bash
# Correct: base64 without data: prefix
base64 -i image.jpg | tr -d '\n'

# Incorrect: includes data: prefix
# data:image/jpeg;base64,iVBORw0...
```

### Batch Processing
- Start with small batches to test
- Monitor `duration_seconds` to optimize batch size
- Check `errors` array for partial failures
- Track `fallback_local` count for OpenAI availability

### Presigned URLs
- URLs expire after configured time (default: 900 seconds)
- Download results before expiration
- Store `object_key` to regenerate URLs if needed

---

## Interactive Documentation

**Swagger UI:**
```
http://localhost:8000/docs
```

**ReDoc:**
```
http://localhost:8000/redoc
```

---

## Related Documentation

- [README.md](README.md) - Quick start and setup
- [CONFIGURATION.md](CONFIGURATION.md) - Environment variables
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
- [tools Orchestrate/README.md](tools%20Orchestrate/README.md) - watsonX Orchestrate integration
