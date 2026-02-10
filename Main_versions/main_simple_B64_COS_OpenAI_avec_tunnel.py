# ==================================================
# Imports
# ==================================================
import os
import io
import re
import base64
import uuid
import mimetypes
from typing import Optional
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

import httpx
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field

from openai import OpenAI

# ==================================================
# Config callback tunnel (comme tu l'avais)
# ==================================================
LOCAL_TUNNEL_NETLOC = "127.0.0.1:14321"

def rewrite_callback_url(callback_url: str) -> str:
    u = urlparse(callback_url)
    if u.hostname == "wxo-server" and (u.port == 4321 or u.port is None):
        u = u._replace(netloc=LOCAL_TUNNEL_NETLOC)
        return urlunparse(u)
    return callback_url

# ==================================================
# COS Config (env vars)
# ==================================================
COS_ENDPOINT = os.getenv("COS_ENDPOINT", "").strip()
COS_REGION = os.getenv("COS_REGION", "eu-geo").strip()
COS_BUCKET = os.getenv("COS_BUCKET", "").strip()
COS_ACCESS_KEY_ID = os.getenv("COS_ACCESS_KEY_ID", "").strip()
COS_SECRET_ACCESS_KEY = os.getenv("COS_SECRET_ACCESS_KEY", "").strip()
COS_PRESIGN_EXPIRES = int(os.getenv("COS_PRESIGN_EXPIRES", "900"))

def _require_cos_config() -> None:
    missing = []
    if not COS_ENDPOINT: missing.append("COS_ENDPOINT")
    if not COS_BUCKET: missing.append("COS_BUCKET")
    if not COS_ACCESS_KEY_ID: missing.append("COS_ACCESS_KEY_ID")
    if not COS_SECRET_ACCESS_KEY: missing.append("COS_SECRET_ACCESS_KEY")
    if missing:
        raise RuntimeError(f"Missing COS env vars: {', '.join(missing)}")

def make_s3_client():
    _require_cos_config()
    cfg = BotoConfig(
        region_name=COS_REGION,
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        retries={"max_attempts": 3, "mode": "standard"},
    )

    return boto3.client(
        "s3",
        endpoint_url=COS_ENDPOINT,
        aws_access_key_id=COS_ACCESS_KEY_ID,
        aws_secret_access_key=COS_SECRET_ACCESS_KEY,
        config=cfg,
    )

# ==================================================
# OpenAI Config (env vars)
# ==================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "medium").strip()   # low|medium|high|auto
OPENAI_IMAGE_OUTPUT_FORMAT = os.getenv("OPENAI_IMAGE_OUTPUT_FORMAT", "png").strip()  # png|jpeg|webp

def _require_openai_config() -> None:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing env var: OPENAI_API_KEY")

def _mime_from_output_format(fmt: str) -> str:
    f = (fmt or "").lower().strip()
    if f in ("jpg", "jpeg"):
        return "image/jpeg"
    if f == "png":
        return "image/png"
    if f == "webp":
        return "image/webp"
    return "application/octet-stream"

def edit_image_with_openai(image_bytes: bytes, prompt: str) -> tuple[bytes, str, str]:
    """
    Calls OpenAI Images Edits API and returns (output_bytes, mime_type, output_ext).
    output_ext derived from OPENAI_IMAGE_OUTPUT_FORMAT.
    """
    _require_openai_config()

    if not prompt or not prompt.strip():
        raise ValueError("prompt vide")

    # File-like; name helps content-type inference server-side
    image_file = io.BytesIO(image_bytes)
    image_file.name = "input.png"

    client = OpenAI(api_key=OPENAI_API_KEY)

    result = client.images.edit(
        model=OPENAI_IMAGE_MODEL,
        image=image_file,
        prompt=prompt,
        quality=OPENAI_IMAGE_QUALITY,
        output_format=OPENAI_IMAGE_OUTPUT_FORMAT,
    )

    b64 = result.data[0].b64_json if result and result.data else None
    if not b64:
        raise RuntimeError("OpenAI returned empty b64_json")

    out_bytes = base64.b64decode(b64)
    output_ext = (OPENAI_IMAGE_OUTPUT_FORMAT or "png").lower().strip()
    mime = _mime_from_output_format(output_ext)

    # normalise ext
    if output_ext == "jpg":
        output_ext = "jpeg"

    return out_bytes, mime, output_ext

# ==================================================
# App
# ==================================================
app = FastAPI(title="WXO Async Image -> COS OR Base64", version="2.1.0")

# ==================================================
# Input schema (WXO)
# ==================================================
class ProcessImageRequest(BaseModel):
    prompt: str = Field(..., description="Instruction de retouche")
    filename: Optional[str] = Field(None, description="Nom du fichier (corrélation)")
    image_base64: str = Field(..., description="Image encodée en base64 (sans data:...)")

# ==================================================
# Callback helper
# ==================================================
async def post_callback(callback_url: str, payload: dict) -> None:
    final_callback_url = rewrite_callback_url(callback_url)
    print("=== CALLBACK ===")
    print("original :", callback_url)
    print("rewritten:", final_callback_url)
    print("keys     :", list(payload.keys()))

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(final_callback_url, json=payload)
        print("status   :", r.status_code)
        r.raise_for_status()

# ==================================================
# Helpers: naming / keys
# ==================================================
def _safe_stem_from_filename(filename: str) -> str:
    # enlève extension
    stem, _ = os.path.splitext(filename)
    stem = stem.strip()
    # safe: espaces + caractères “bizarres”
    stem = stem.replace(" ", "_")
    stem = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", stem)
    stem = stem.strip("._-") or "image"
    return stem

def make_object_key(job_id: str, filename: Optional[str], output_ext: str) -> str:
    """
    Keep your original structure: results/{job_id}/...
    But avoid burger.jpeg.png by removing original extension first.
    """
    stem = _safe_stem_from_filename(filename) if filename else f"image_{job_id[:8]}"
    return f"results/{job_id}/{stem}_modified.{output_ext}"

# ==================================================
# COS: upload + presign
# ==================================================
def upload_and_presign(result_bytes: bytes, object_key: str, content_type: str) -> str:
    s3 = make_s3_client()

    try:
        s3.put_object(
            Bucket=COS_BUCKET,
            Key=object_key,
            Body=result_bytes,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"COS put_object failed: {type(e).__name__}: {e}")

    try:
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": COS_BUCKET, "Key": object_key},
            ExpiresIn=COS_PRESIGN_EXPIRES,
        )
        return url
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"COS presign failed: {type(e).__name__}: {e}")

# ==================================================
# Background job A: decode -> OpenAI -> COS -> callback(URL)
# ==================================================
async def process_and_callback_url(job_id: str, req: ProcessImageRequest, callback_url: str) -> None:
    print("\n=== JOB START (URL) ===")
    print("job_id   :", job_id)
    print("filename :", req.filename)
    print("prompt   :", (req.prompt or "")[:200])
    print("b64_len  :", len(req.image_base64 or ""))

    try:
        # 1) base64 -> bytes
        try:
            image_bytes = base64.b64decode(req.image_base64, validate=True)
        except Exception:
            raise ValueError("image_base64 invalide (base64 attendu, sans préfixe data:...)")

        if not req.prompt or not req.prompt.strip():
            raise ValueError("prompt vide")

        # 2) traitement via OpenAI
        result_bytes, result_mime, output_ext = edit_image_with_openai(image_bytes, req.prompt)

        # 3) upload + presign
        object_key = make_object_key(job_id, req.filename, output_ext=output_ext)
        presigned_url = upload_and_presign(result_bytes, object_key, result_mime)

        payload = {
            "status": "completed",
            "job_id": job_id,
            "filename": req.filename,
            "object_key": object_key,
            "result_url": presigned_url,
            "expires_in": COS_PRESIGN_EXPIRES,
        }
        await post_callback(callback_url, payload)

        print("=== JOB DONE (URL) ===", job_id)

    except Exception as e:
        payload = {
            "status": "failed",
            "job_id": job_id,
            "filename": req.filename,
            "error": f"{type(e).__name__}: {e}",
        }
        try:
            await post_callback(callback_url, payload)
        except Exception as cb_err:
            print("!!! CALLBACK FAILED (URL) !!!", repr(cb_err))

# ==================================================
# Background job B: decode -> OpenAI -> callback(BASE64)
# ==================================================
async def process_and_callback_b64(job_id: str, req: ProcessImageRequest, callback_url: str) -> None:
    print("\n=== JOB START (B64) ===")
    print("job_id   :", job_id)
    print("filename :", req.filename)
    print("prompt   :", (req.prompt or "")[:200])
    print("b64_len  :", len(req.image_base64 or ""))

    try:
        # 1) base64 -> bytes
        try:
            image_bytes = base64.b64decode(req.image_base64, validate=True)
        except Exception:
            raise ValueError("image_base64 invalide (base64 attendu, sans préfixe data:...)")

        if not req.prompt or not req.prompt.strip():
            raise ValueError("prompt vide")

        # 2) traitement via OpenAI
        result_bytes, result_mime, _output_ext = edit_image_with_openai(image_bytes, req.prompt)

        # 3) bytes -> base64
        result_b64 = base64.b64encode(result_bytes).decode("ascii")

        payload = {
            "status": "completed",
            "job_id": job_id,
            "filename": req.filename,
            "result_image_base64": result_b64,
            "result_mime_type": result_mime,
        }
        await post_callback(callback_url, payload)

        print("=== JOB DONE (B64) ===", job_id)

    except Exception as e:
        payload = {
            "status": "failed",
            "job_id": job_id,
            "filename": req.filename,
            "error": f"{type(e).__name__}: {e}",
        }
        try:
            await post_callback(callback_url, payload)
        except Exception as cb_err:
            print("!!! CALLBACK FAILED (B64) !!!", repr(cb_err))

# ==================================================
# Endpoint 1 (WXO): async -> callback URL (COS)
# ==================================================
@app.post("/process-image-async", status_code=202)
async def process_image_async(
    body: ProcessImageRequest,
    background_tasks: BackgroundTasks,
    callbackUrl: str = Header(...),
):
    # Vérif COS config dès l'appel (sinon WXO attendra un callback qui ne viendra pas)
    try:
        _require_cos_config()
        _require_openai_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    job_id = str(uuid.uuid4())
    background_tasks.add_task(process_and_callback_url, job_id, body, callbackUrl)
    return {"accepted": True, "job_id": job_id}

# ==================================================
# Endpoint 2 (WXO): async -> callback BASE64 (sans COS)
# ==================================================
@app.post("/process-image-async-b64", status_code=202)
async def process_image_async_b64(
    body: ProcessImageRequest,
    background_tasks: BackgroundTasks,
    callbackUrl: str = Header(...),
):
    try:
        _require_openai_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    job_id = str(uuid.uuid4())
    background_tasks.add_task(process_and_callback_b64, job_id, body, callbackUrl)
    return {"accepted": True, "job_id": job_id}

# ==================================================
# Healthcheck
# ==================================================
@app.get("/health")
def health():
    return {"ok": True}

# ==================================================
# COS health/config
# ==================================================
@app.get("/cos/health")
def cos_health():
    try:
        s3 = make_s3_client()
        s3.head_bucket(Bucket=COS_BUCKET)
        return {"ok": True, "bucket": COS_BUCKET}
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        raise HTTPException(status_code=500, detail=f"COS health failed: {code}: {msg}")

@app.get("/cos/config")
def cos_config():
    return {
        "endpoint": COS_ENDPOINT,
        "region": COS_REGION,
        "bucket": COS_BUCKET,
        "access_key_id_prefix": (COS_ACCESS_KEY_ID[:4] + "...") if COS_ACCESS_KEY_ID else "",
    }

# ==================================================
# Debug: synchro (retour direct URL) - utile pour tester OpenAI + COS
# ==================================================
@app.post("/debug/process-image-sync")
def debug_process_image_sync(body: ProcessImageRequest):
    try:
        _require_cos_config()
        _require_openai_config()

        image_bytes = base64.b64decode(body.image_base64, validate=True)

        result_bytes, result_mime, output_ext = edit_image_with_openai(image_bytes, body.prompt)

        job_id = str(uuid.uuid4())
        object_key = make_object_key(job_id, body.filename, output_ext=output_ext)
        presigned_url = upload_and_presign(result_bytes, object_key, result_mime)

        return {"ok": True, "object_key": object_key, "url": presigned_url, "expires_in": COS_PRESIGN_EXPIRES}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@app.post("/debug/openai-edit-b64")
def debug_openai_edit_b64(body: ProcessImageRequest):
    try:
        _require_openai_config()
        image_bytes = base64.b64decode(body.image_base64, validate=True)
        result_bytes, result_mime, _ext = edit_image_with_openai(image_bytes, body.prompt)
        return {
            "ok": True,
            "result_mime_type": result_mime,
            "result_image_base64": base64.b64encode(result_bytes).decode("ascii"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
