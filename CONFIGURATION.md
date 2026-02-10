# ⚙️ Configuration Guide

Complete configuration reference for the WXO Asynchronous Image Processing service.

> **📚 Related Documentation:**
> [README.md](README.md) · [API.md](API.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [tools Orchestrate/README.md](tools%20Orchestrate/README.md)

---

## Environment Variables

All configuration is managed through environment variables following the [12-factor app](https://12factor.net/) methodology.

### Quick Setup

1. Copy the example file:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials

3. Load variables:
```bash
set -a
source .env
set +a
```

---

## IBM Cloud Object Storage

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `COS_ENDPOINT` | COS endpoint URL (region-specific) | `https://s3.eu-de.cloud-object-storage.appdomain.cloud` |
| `COS_REGION` | COS region code | `eu-de`, `us-south`, `us-east` |
| `COS_ACCESS_KEY_ID` | HMAC access key ID | Get from IBM Cloud Console → Object Storage → Service Credentials |
| `COS_SECRET_ACCESS_KEY` | HMAC secret access key | Get from IBM Cloud Console → Object Storage → Service Credentials |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COS_BUCKET` | - | Default bucket (legacy, used as fallback) |
| `COS_PRESIGN_EXPIRES` | `900` | Presigned URL expiration time in seconds (15 minutes) |

### Regional Endpoints

| Region | Endpoint |
|--------|----------|
| EU Germany | `https://s3.eu-de.cloud-object-storage.appdomain.cloud` |
| US South | `https://s3.us-south.cloud-object-storage.appdomain.cloud` |
| US East | `https://s3.us-east.cloud-object-storage.appdomain.cloud` |
| UK | `https://s3.eu-gb.cloud-object-storage.appdomain.cloud` |

[Full list of endpoints](https://cloud.ibm.com/docs/cloud-object-storage?topic=cloud-object-storage-endpoints)

---

## Batch Processing Configuration

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `COS_INPUT_BUCKET` | Bucket containing source images | `input-images` |
| `COS_OUTPUT_BUCKET` | Bucket where processed images will be stored | `wxo-images` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COS_INPUT_PREFIX` | `""` | Folder path in input bucket (e.g., `demo/` or `images/raw/`) |
| `COS_OUTPUT_PREFIX` | `results/batch` | Base folder path in output bucket<br>Results stored as: `{OUTPUT_PREFIX}/{job_id}/` |

### Example Structure

```
Input Bucket (input-images):
├── image1.jpg
├── image2.png
└── subfolder/
    └── image3.jpg

Output Bucket (wxo-images):
└── results/batch/
    └── 550e8400-e29b-41d4-a716-446655440000/
        ├── image1_modified.png
        ├── image2_modified.png
        └── image3_modified.png
```

---

## OpenAI Configuration

### Required Variables

| Variable | Description | How to Get |
|----------|-------------|------------|
| `OPENAI_API_KEY` | OpenAI API key | https://platform.openai.com/api-keys |

### Optional Variables

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `OPENAI_IMAGE_MODEL` | `gpt-image-1` | Check [OpenAI docs](https://platform.openai.com/docs/models) | Image model to use |
| `OPENAI_IMAGE_QUALITY` | `high` | `low`, `medium`, `high`, `auto` | Image quality setting |
| `OPENAI_IMAGE_OUTPUT_FORMAT` | `png` | `png`, `jpeg`, `webp` | Output image format |

---

## Complete .env Example

```bash
# ==================================================
# IBM Cloud Object Storage Configuration
# ==================================================

# COS Endpoint (region-specific)
COS_ENDPOINT=https://s3.eu-de.cloud-object-storage.appdomain.cloud

# COS Region
COS_REGION=eu-de

# Default bucket (legacy, used as fallback)
COS_BUCKET=wxo-images

# COS Credentials (HMAC)
COS_ACCESS_KEY_ID=your_access_key_id_here
COS_SECRET_ACCESS_KEY=your_secret_access_key_here

# Presigned URL expiration time (in seconds)
COS_PRESIGN_EXPIRES=900

# ==================================================
# Batch Processing Configuration
# ==================================================

# Input bucket (where source images are stored)
COS_INPUT_BUCKET=input-images

# Output bucket (where processed images will be stored)
COS_OUTPUT_BUCKET=wxo-images

# Input prefix (folder path in input bucket, optional)
COS_INPUT_PREFIX=

# Output prefix (folder path in output bucket)
COS_OUTPUT_PREFIX=results/batch

# ==================================================
# OpenAI Configuration
# ==================================================

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Image model to use
OPENAI_IMAGE_MODEL=gpt-image-1

# Image quality
OPENAI_IMAGE_QUALITY=high

# Output format
OPENAI_IMAGE_OUTPUT_FORMAT=png
```

---

## Getting IBM Cloud Credentials

### Step 1: Create Service Credentials

1. Go to [IBM Cloud Console](https://cloud.ibm.com/)
2. Navigate to **Object Storage** → Your instance
3. Click **Service Credentials** in the left menu
4. Click **New Credential**
5. Enable **Include HMAC Credential** toggle
6. Click **Add**

### Step 2: Extract Values

From the generated credentials JSON:

```json
{
  "apikey": "...",
  "cos_hmac_keys": {
    "access_key_id": "← Use this for COS_ACCESS_KEY_ID",
    "secret_access_key": "← Use this for COS_SECRET_ACCESS_KEY"
  },
  "endpoints": "https://control.cloud-object-storage.cloud.ibm.com/v2/endpoints",
  "iam_apikey_description": "...",
  "iam_apikey_name": "...",
  "iam_role_crn": "...",
  "iam_serviceid_crn": "...",
  "resource_instance_id": "..."
}
```

### Step 3: Find Your Endpoint

1. Visit the endpoints URL from credentials
2. Choose your region (e.g., `eu-de`)
3. Use the **public** endpoint for `COS_ENDPOINT`

---

## Validation

### Test COS Configuration

```bash
curl http://localhost:8000/cos/config
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

### Test Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"ok": true}
```

---

## Troubleshooting

### Missing Environment Variables

**Error:**
```
RuntimeError: Missing COS env vars: COS_ENDPOINT, COS_ACCESS_KEY_ID
```

**Solution:**
1. Verify `.env` file exists
2. Check variable names (case-sensitive)
3. Reload environment: `set -a && source .env && set +a`

### Invalid Credentials

**Error:**
```
ClientError: An error occurred (InvalidAccessKeyId) when calling the ListObjects operation
```

**Solution:**
1. Verify HMAC credentials are enabled in IBM Cloud
2. Check `COS_ACCESS_KEY_ID` and `COS_SECRET_ACCESS_KEY`
3. Ensure credentials haven't expired

### Wrong Endpoint

**Error:**
```
EndpointConnectionError: Could not connect to the endpoint URL
```

**Solution:**
1. Verify `COS_ENDPOINT` matches your region
2. Check network connectivity
3. Ensure endpoint includes `https://`

### Bucket Not Found

**Error:**
```
NoSuchBucket: The specified bucket does not exist
```

**Solution:**
1. Verify bucket names in `COS_INPUT_BUCKET` and `COS_OUTPUT_BUCKET`
2. Check bucket exists in IBM Cloud Console
3. Ensure credentials have access to the bucket

---

## Security Best Practices

### Development

✅ Use `.env` file (never commit to git)  
✅ Add `.env` to `.gitignore`  
✅ Use `.env.example` as template  
✅ Rotate credentials regularly

### Production

✅ Use secrets management service (AWS Secrets Manager, IBM Key Protect)  
✅ Implement credential rotation  
✅ Use IAM roles instead of static credentials when possible  
✅ Audit access logs regularly  
✅ Limit credential scope to minimum required permissions

---

## Related Documentation

- [README.md](README.md) - Quick start guide
- [API.md](API.md) - API reference
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
- [IBM Cloud Object Storage Docs](https://cloud.ibm.com/docs/cloud-object-storage)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)