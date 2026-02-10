# WXO -> Mac ->traitement -> tunnel -> Wxo (Pour travail en local: renvoie un Base64)

#ssh -o 'IdentityFile="/Users/francoisestepa/.lima/_config/user"' \
#  -o StrictHostKeyChecking=no \
#  -o UserKnownHostsFile=/dev/null \
#  -o NoHostAuthenticationForLocalhost=yes \
#  -o PreferredAuthentications=publickey \
#  -o Compression=no \
#  -o BatchMode=yes \
#  -o IdentitiesOnly=yes \
#  -o GSSAPIAuthentication=no \
#  -o 'Ciphers="^aes128-gcm@openssh.com,aes256-gcm@openssh.com"' \
#  -o User=francoisestepa \
#  -o ControlMaster=auto \
#  -o 'ControlPath="/Users/francoisestepa/.lima/ibm-watsonx-orchestrate/ssh.sock"' \
#  -o ControlPersist=yes \
#  -o Hostname=127.0.0.1 \
#  -o Port=55782 \
#  -N \
#  -L 14321:127.0.0.1:4321 \
#  lima-ibm-watsonx-orchestrate


# ==================================================
# Imports
# ==================================================
import base64
import uuid
from typing import Optional
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field

from PIL import Image, ImageOps
import io

# ==================================================
# Config (tunnel callback WXO via SSH port-forward)
# - WXO te fournit callbackUrl = http://wxo-server:4321/...
# - macOS ne résout pas wxo-server, donc on réécrit vers le tunnel local:
#   http://127.0.0.1:14321/...
# ==================================================
LOCAL_TUNNEL_NETLOC = "127.0.0.1:14321"

def rewrite_callback_url(callback_url: str) -> str:
    """
    Réécrit le callbackUrl fourni par WXO (host interne 'wxo-server:4321')
    vers le tunnel local sur macOS (127.0.0.1:14321).
    """
    u = urlparse(callback_url)

    # Cas attendu: http://wxo-server:4321/...
    if u.hostname == "wxo-server" and (u.port == 4321 or u.port is None):
        u = u._replace(netloc=LOCAL_TUNNEL_NETLOC)
        return urlunparse(u)

    return callback_url

# ==================================================
# App
# ==================================================
app = FastAPI(title="WXO Async Image Processing Tool", version="1.0.0")

# ==================================================
# Input schema (ce que WXO envoie en appel)
# ==================================================
class ProcessImageRequest(BaseModel):
    prompt: str = Field(..., description="Instruction de retouche")
    filename: Optional[str] = Field(None, description="Nom du fichier (pour la corrélation)")
    image_base64: str = Field(..., description="Image encodée en base64 (sans data:...)")

# ==================================================
# Callback helper (POST JSON vers WXO callbackUrl)
# ==================================================
async def post_callback(callback_url: str, payload: dict, job_id: str) -> None:
    final_callback_url = rewrite_callback_url(callback_url)

    print("\n=== CALLBACK ATTEMPT ===")
    print("job_id     :", job_id)
    print("original   :", callback_url)
    print("rewritten  :", final_callback_url)
    print("payloadKeys:", list(payload.keys()))
    # éviter d'imprimer l'image base64 (trop gros) — juste une taille
    if "result_image_base64" in payload and isinstance(payload["result_image_base64"], str):
        print("result_image_base64_len:", len(payload["result_image_base64"]))
    print("========================\n")

    timeout = httpx.Timeout(30.0, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(final_callback_url, json=payload)

            print("=== CALLBACK RESPONSE ===")
            print("job_id  :", job_id)
            print("status  :", r.status_code)
            print("body300 :", r.text[:300])
            print("========================\n")

            r.raise_for_status()

    except httpx.ConnectError as e:
        print("!!! CALLBACK CONNECT ERROR !!!")
        print("job_id :", job_id)
        print("url    :", final_callback_url)
        print("error  :", repr(e))
        raise

    except httpx.ReadTimeout as e:
        print("!!! CALLBACK TIMEOUT !!!")
        print("job_id :", job_id)
        print("url    :", final_callback_url)
        print("error  :", repr(e))
        raise

    except httpx.HTTPStatusError as e:
        # 4xx / 5xx
        resp = e.response
        print("!!! CALLBACK HTTP ERROR !!!")
        print("job_id :", job_id)
        print("url    :", final_callback_url)
        print("status :", resp.status_code)
        print("body300:", resp.text[:300])
        raise

    except Exception as e:
        print("!!! CALLBACK UNKNOWN ERROR !!!")
        print("job_id :", job_id)
        print("url    :", final_callback_url)
        print("error  :", repr(e))
        raise

# ==================================================
# Traitement (stub) - à remplacer par OpenAI ou Gemini
# ==================================================
def beautify_image_stub(image_bytes: bytes, prompt: str) -> bytes:
    """
    Inverse les couleurs de l'image reçue.
    Retourne des BYTES.
    """

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.invert(img)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ==================================================
# Background job: traite + callback
# ==================================================
async def process_and_callback(job_id: str, req: ProcessImageRequest, callback_url: str) -> None:
    try:
        print("\n=== JOB START ===")
        print("job_id  :", job_id)
        print("filename:", req.filename)
        print("prompt  :", (req.prompt or "")[:120])
        print("image_base64_len:", len(req.image_base64) if isinstance(req.image_base64, str) else "n/a")
        print("==============\n")

        # 1) base64 -> bytes
        try:
            image_bytes = base64.b64decode(req.image_base64, validate=True)
        except Exception:
            raise ValueError("image_base64 invalide (base64 attendu, sans préfixe data:...)")

        if not req.prompt or not req.prompt.strip():
            raise ValueError("prompt vide")

        # 2) traitement (à remplacer)
        result_bytes = beautify_image_stub(image_bytes, req.prompt)

        # 3) bytes -> base64
        result_b64 = base64.b64encode(result_bytes).decode("utf-8")

        payload = {
            "status": "completed",
            "job_id": job_id,
            "filename": req.filename,
            "result_image_base64": result_b64,
        }

        await post_callback(callback_url, payload, job_id)

        print("=== JOB DONE ===")
        print("job_id:", job_id)
        print("==============\n")

    except Exception as e:
        payload = {
            "status": "failed",
            "job_id": job_id,
            "filename": req.filename,
            "error": f"{type(e).__name__}: {e}",
        }

        # Toujours essayer de rappeler WXO, même en erreur
        try:
            await post_callback(callback_url, payload, job_id)
        except Exception as cb_err:
            print("!!! CALLBACK FAILED EVEN AFTER REWRITE !!!")
            print("job_id:", job_id)
            print("error :", repr(cb_err))

# ==================================================
# Endpoint appelé par WXO
# ==================================================
@app.post("/process-image-async", status_code=202)
async def process_image_async(
    body: ProcessImageRequest,
    background_tasks: BackgroundTasks,
    callbackUrl: str = Header(..., description="Header EXACT requis par WXO: callbackUrl"),
):
    # job_id pour tracer la requête
    job_id = str(uuid.uuid4())

    print("\n=== RECEIVED /process-image-async ===")
    print("job_id     :", job_id)
    print("callbackUrl:", callbackUrl)
    print("====================================\n")

    # Lancer le job après la réponse 202
    background_tasks.add_task(process_and_callback, job_id, body, callbackUrl)

    # Réponse immédiate à WXO
    return {"accepted": True, "job_id": job_id}

# ==================================================
# Healthcheck
# ==================================================
@app.get("/health")
def health():
    return {"ok": True}
