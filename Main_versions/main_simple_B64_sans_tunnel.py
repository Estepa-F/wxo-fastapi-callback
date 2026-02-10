# ==================================================
# Imports
# ==================================================
import base64
import uuid
from typing import Optional

import httpx
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field

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
# Callback helper (POST JSON vers WXO callbackUrl pour envoyer le résultat de OpenAI/Gemini)
# ==================================================
async def post_callback(callback_url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(callback_url, json=payload)
        r.raise_for_status()

# ==================================================
# Traitement (stub) - à remplacer par OpenAI ou Gemini
# ==================================================
def beautify_image_stub(image_bytes: bytes, prompt: str) -> bytes:
    """
    Workshop stub: renvoie l'image inchangée.
    Remplace cette fonction par l'appel OpenAI (image edit/variation) + récupération du binaire résultat.
    """
    return image_bytes

# ==================================================
# Background job: traite + callback
# ==================================================
async def process_and_callback(job_id: str, req: ProcessImageRequest, callback_url: str) -> None:
    try:
        # 1) base64 -> bytes
        try:
            image_bytes = base64.b64decode(req.image_base64, validate=True)
        except Exception:
            raise ValueError("image_base64 invalide (base64 attendu, sans préfixe data:...)")

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
        await post_callback(callback_url, payload)

    except Exception as e:
        payload = {
            "status": "failed",
            "job_id": job_id,
            "filename": req.filename,
            "error": str(e),
        }
        # Toujours essayer de rappeler WXO, même en erreur
        try:
            await post_callback(callback_url, payload)
        except Exception:
            pass

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

    # Lancer le job après la réponse 202
    background_tasks.add_task(process_and_callback, job_id, body, callbackUrl)

    # Réponse immédiate à WXO
    return {"accepted": True, "job_id": job_id}


@app.get("/health")
def health():
    return {"ok": True}
