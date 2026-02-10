# ==================================================
# Imports
# ==================================================
import os
import io
import re
import time
import base64
import uuid
from typing import Optional, List
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

import httpx
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field

from openai import OpenAI

# Fallback local
from PIL import Image, ImageOps, ImageDraw, ImageFont


# ==================================================
# Config callback tunnel (Mac/Lima) - inchangé
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
COS_BUCKET = os.getenv("COS_BUCKET", "").strip()  # historique

COS_ACCESS_KEY_ID = os.getenv("COS_ACCESS_KEY_ID", "").strip()
COS_SECRET_ACCESS_KEY = os.getenv("COS_SECRET_ACCESS_KEY", "").strip()
COS_PRESIGN_EXPIRES = int(os.getenv("COS_PRESIGN_EXPIRES", "900"))

# Batch (entrée/sortie)
COS_INPUT_BUCKET = os.getenv("COS_INPUT_BUCKET", "").strip()                 # ex: input-images
COS_OUTPUT_BUCKET = os.getenv("COS_OUTPUT_BUCKET", COS_BUCKET).strip()       # ex: wxo-images
COS_INPUT_PREFIX = os.getenv("COS_INPUT_PREFIX", "").strip()                 # ex: demo/
COS_OUTPUT_PREFIX = os.getenv("COS_OUTPUT_PREFIX", "results/batch").strip()  # ex: results/batch

def _require_cos_config() -> None:
    missing = []
    if not COS_ENDPOINT: missing.append("COS_ENDPOINT")
    if not COS_ACCESS_KEY_ID: missing.append("COS_ACCESS_KEY_ID")
    if not COS_SECRET_ACCESS_KEY: missing.append("COS_SECRET_ACCESS_KEY")
    if not COS_OUTPUT_BUCKET: missing.append("COS_OUTPUT_BUCKET (or COS_BUCKET)")
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
OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "medium").strip()          # low|medium|high|auto
OPENAI_IMAGE_OUTPUT_FORMAT = os.getenv("OPENAI_IMAGE_OUTPUT_FORMAT", "png").strip() # png|jpeg|webp

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
    Returns (output_bytes, mime_type, output_ext)
    """
    _require_openai_config()
    if not prompt or not prompt.strip():
        raise ValueError("prompt vide")

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
    if output_ext == "jpg":
        output_ext = "jpeg"
    mime = _mime_from_output_format(output_ext)
    return out_bytes, mime, output_ext


# ==================================================
# Fallback local
# ==================================================
def local_fallback_process(image_bytes: bytes) -> tuple[bytes, str, str]:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = ImageOps.invert(img.convert("RGB")).convert("RGBA")

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text = "DEMO - FALLBACK (OpenAI billing limit)"
    # Police par défaut (pas besoin de fichier .ttf)
    draw.text((20, 20), text, fill=(255, 0, 0, 200))

    img = Image.alpha_composite(img, overlay)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue(), "image/png", "png"


# ==================================================
# App
# ==================================================
app = FastAPI(title="WXO Async Image Tools", version="3.1.0")


# ==================================================
# Input schemas
# ==================================================
class ProcessImageRequest(BaseModel):
    prompt: str = Field(..., description="Instruction de retouche")
    filename: Optional[str] = Field(None, description="Nom du fichier (corrélation)")
    image_base64: str = Field(..., description="Image encodée en base64 (sans data:...)")

class BatchProcessRequest(BaseModel):
    prompt: str = Field(..., description="Instruction appliquée à toutes les images du bucket input")


# ==================================================
# Callback helper
# ==================================================
async def post_callback(callback_url: str, payload: dict) -> None:
    final_callback_url = rewrite_callback_url(callback_url)
    print("=== CALLBACK ===")
    print("original :", callback_url)
    print("rewritten:", final_callback_url)
    print("keys     :", list(payload.keys()))

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(final_callback_url, json=payload)
        print("status   :", r.status_code)
        r.raise_for_status()


# ==================================================
# Helpers: naming
# ==================================================
def _safe_stem_from_filename(filename: str) -> str:
    stem, _ = os.path.splitext(filename)
    stem = stem.strip().replace(" ", "_")
    stem = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", stem)
    stem = stem.strip("._-") or "image"
    return stem

def make_object_key(job_id: str, filename: Optional[str], output_ext: str) -> str:
    stem = _safe_stem_from_filename(filename) if filename else f"image_{job_id[:8]}"
    return f"results/{job_id}/{stem}_modified.{output_ext}"

def make_batch_output_key(job_id: str, input_key: str, output_ext: str) -> str:
    filename = os.path.basename(input_key)
    stem = _safe_stem_from_filename(filename)
    return f"{COS_OUTPUT_PREFIX}/{job_id}/{stem}_modified.{output_ext}"


# ==================================================
# COS helpers
# ==================================================
def upload_and_presign(result_bytes: bytes, object_key: str, content_type: str, bucket: str) -> str:
    s3 = make_s3_client()

    try:
        s3.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=result_bytes,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"COS put_object failed: {type(e).__name__}: {e}")

    try:
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=COS_PRESIGN_EXPIRES,
        )
        return url
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"COS presign failed: {type(e).__name__}: {e}")

def list_input_objects(prefix: str = "") -> List[str]:
    if not COS_INPUT_BUCKET:
        raise RuntimeError("Missing env var: COS_INPUT_BUCKET")

    s3 = make_s3_client()
    keys: List[str] = []
    token = None

    while True:
        kwargs = {"Bucket": COS_INPUT_BUCKET}
        if prefix:
            kwargs["Prefix"] = prefix
        if token:
            kwargs["ContinuationToken"] = token

        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            k = obj.get("Key")
            if k and not k.endswith("/"):
                keys.append(k)

        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
        else:
            break

    return keys

def get_object_bytes(bucket: str, key: str) -> bytes:
    s3 = make_s3_client()
    resp = s3.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()

def put_object_bytes(bucket: str, key: str, data: bytes, content_type: str) -> None:
    s3 = make_s3_client()
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


# ==================================================
# Background job A: single image -> COS URL
# ==================================================
async def process_and_callback_url(job_id: str, req: ProcessImageRequest, callback_url: str) -> None:
    try:
        try:
            image_bytes = base64.b64decode(req.image_base64, validate=True)
        except Exception:
            payload = {
                "status": "failed",
                "job_id": job_id,
                "filename": req.filename,
                "error": "ValueError: image_base64 invalide (base64 attendu, sans préfixe data:...)",
            }
            await post_callback(callback_url, payload)
            return

        # OpenAI (pas de fallback ici par défaut ; tu peux l'ajouter aussi si tu veux)
        result_bytes, result_mime, output_ext = edit_image_with_openai(image_bytes, req.prompt)
        object_key = make_object_key(job_id, req.filename, output_ext=output_ext)
        presigned_url = upload_and_presign(result_bytes, object_key, result_mime, bucket=COS_OUTPUT_BUCKET)

        payload = {
            "status": "completed",
            "job_id": job_id,
            "filename": req.filename,
            "object_key": object_key,
            "result_url": presigned_url,
            "expires_in": COS_PRESIGN_EXPIRES,
        }
        await post_callback(callback_url, payload)

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
            print("!!! CALLBACK FAILED (SINGLE URL) !!!", repr(cb_err))


# ==================================================
# Background job B: single image -> Base64
# ==================================================
async def process_and_callback_b64(job_id: str, req: ProcessImageRequest, callback_url: str) -> None:
    try:
        try:
            image_bytes = base64.b64decode(req.image_base64, validate=True)
        except Exception:
            payload = {
                "status": "failed",
                "job_id": job_id,
                "filename": req.filename,
                "error": "ValueError: image_base64 invalide (base64 attendu, sans préfixe data:...)",
            }
            await post_callback(callback_url, payload)
            return

        result_bytes, result_mime, _ext = edit_image_with_openai(image_bytes, req.prompt)
        result_b64 = base64.b64encode(result_bytes).decode("ascii")

        payload = {
            "status": "completed",
            "job_id": job_id,
            "filename": req.filename,
            "result_image_base64": result_b64,
            "result_mime_type": result_mime,
        }
        await post_callback(callback_url, payload)

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
            print("!!! CALLBACK FAILED (SINGLE B64) !!!", repr(cb_err))


# ==================================================
# Background job C: batch input-images -> output bucket
# (one callback only + metrics + Option A fallback local)
# ==================================================
async def batch_process_and_callback(job_id: str, req: BatchProcessRequest, callback_url: str) -> None:
    start = time.perf_counter()

    processed = 0
    failed = 0
    total_files = 0
    fallback_local = 0
    errors: List[str] = []

    status = "failed"
    error_message: Optional[str] = None

    try:
        if not COS_INPUT_BUCKET:
            raise RuntimeError("Missing env var: COS_INPUT_BUCKET")
        if not req.prompt or not req.prompt.strip():
            raise ValueError("prompt vide")

        keys = list_input_objects(prefix=COS_INPUT_PREFIX)
        total_files = len(keys)

        if total_files == 0:
            status = "completed"
        else:
            for k in keys:
                img_bytes = b""
                try:
                    img_bytes = get_object_bytes(COS_INPUT_BUCKET, k)

                    # 1) tentative OpenAI
                    out_bytes, out_mime, out_ext = edit_image_with_openai(img_bytes, req.prompt)

                except Exception as e:
                    msg = f"{type(e).__name__}: {e}"

                    # 2) Option A: fallback local si billing hard limit
                    if "billing_hard_limit_reached" in msg or "Billing hard limit has been reached" in msg:
                        try:
                            out_bytes, out_mime, out_ext = local_fallback_process(img_bytes)
                            fallback_local += 1
                            errors.append(f"{k}: OpenAI billing limit -> fallback local applied")
                        except Exception as e2:
                            failed += 1
                            errors.append(f"{k}: fallback local failed: {type(e2).__name__}: {e2}")
                            continue
                    else:
                        failed += 1
                        errors.append(f"{k}: {msg}")
                        continue

                # 3) upload résultat (OpenAI ou fallback)
                try:
                    out_key = make_batch_output_key(job_id, k, out_ext)
                    put_object_bytes(COS_OUTPUT_BUCKET, out_key, out_bytes, out_mime)
                    processed += 1
                except Exception as e3:
                    failed += 1
                    errors.append(f"{k}: upload failed: {type(e3).__name__}: {e3}")

            status = "completed" if failed == 0 else "completed_with_errors"

    except Exception as e:
        status = "failed"
        error_message = f"{type(e).__name__}: {e}"

    duration_seconds = round(time.perf_counter() - start, 3)
    avg_seconds_per_file = round(duration_seconds / max(total_files, 1), 3) if total_files else None

    payload = {
        "status": status,
        "job_id": job_id,
        "total_files": total_files,
        "processed": processed,
        "failed": failed,
        "fallback_local": fallback_local,
        "duration_seconds": duration_seconds,
        "total_files_processed": processed + fallback_local,
        "output_bucket": COS_OUTPUT_BUCKET,
        "output_prefix": f"{COS_OUTPUT_PREFIX}/{job_id}/",
        "errors": errors[:20],
    }
    if error_message:
        payload["error"] = error_message

    try:
        await post_callback(callback_url, payload)
    except Exception as cb_err:
        print("!!! CALLBACK FAILED (BATCH) !!!", repr(cb_err))


# ==================================================
# Endpoints
# ==================================================
@app.post("/process-image-async", status_code=202)
async def process_image_async(
    body: ProcessImageRequest,
    background_tasks: BackgroundTasks,
    callbackUrl: str = Header(...),
):
    try:
        _require_cos_config()
        _require_openai_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    job_id = str(uuid.uuid4())
    background_tasks.add_task(process_and_callback_url, job_id, body, callbackUrl)
    return {"accepted": True, "job_id": job_id}


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


@app.post("/batch-process-images", status_code=202)
async def batch_process_images(
    body: BatchProcessRequest,
    background_tasks: BackgroundTasks,
    callbackUrl: str = Header(...),
):
    try:
        _require_cos_config()
        _require_openai_config()
        if not COS_INPUT_BUCKET:
            raise RuntimeError("Missing env var: COS_INPUT_BUCKET")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    job_id = str(uuid.uuid4())
    background_tasks.add_task(batch_process_and_callback, job_id, body, callbackUrl)
    return {"accepted": True, "job_id": job_id}


# ==================================================
# Health / Config
# ==================================================
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/cos/config")
def cos_config():
    return {
        "endpoint": COS_ENDPOINT,
        "region": COS_REGION,
        "input_bucket": COS_INPUT_BUCKET,
        "output_bucket": COS_OUTPUT_BUCKET,
        "input_prefix": COS_INPUT_PREFIX,
        "output_prefix": COS_OUTPUT_PREFIX,
        "presign_expires": COS_PRESIGN_EXPIRES,
    }
