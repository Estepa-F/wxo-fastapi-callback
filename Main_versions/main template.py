# ==================================================
# Imports
# ==================================================

import uuid # Sert à générer un identifiant unique -> request_id
#from typing import Optional

import httpx # pour faire des requêtes HTTP sortantes -> callbackURL
from fastapi import (
    FastAPI, # créer l’application
    BackgroundTasks, # lancer du code après la réponse
    Header, # lire un header HTTP
    UploadFile, # recevoir un fichier
    File, # dire que c’est un fichier
    Form, # lire un champ de formulaire
)
from fastapi.responses import JSONResponse # Permet de choisir le code HTTP (ici 202) et le contenu JSON

# ==================================================
# Application setup
# ==================================================

#Création de l'application FastAPI 
app = FastAPI(title="WXO Async Callback Tool Server")

# ⚠️ Démo: traitement "fake". Remplace par ton vrai traitement (OpenAI image edit, etc.)
async def do_image_processing(image_bytes: bytes, prompt: str) -> dict:
    # Ici tu ferais ton appel OpenAI / traitement IA / etc.
    # On retourne un résultat simulé.
    return {
        "status": "success",
        "prompt_used": prompt,
        "result": {
            "message": "Traitement terminé",
            # Exemple: si tu veux renvoyer une image, tu peux renvoyer une URL,
            # ou une image en base64 (si WXO l’accepte dans ton schéma).
            "image_url": "https://example.com/fake-image.png",
        }
    }

# Envoyer le callback vers WXO
async def post_callback(callback_url: str, payload: dict) -> None:
    # POST JSON vers WXO (callbackUrl)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(callback_url, json=payload)
        r.raise_for_status()

# fonction centrale : traitement + callback
async def process_and_callback(callback_url: str, image_bytes: bytes, prompt: str, request_id: str) -> None:
    try:
        result = await do_image_processing(image_bytes, prompt)
        payload = {
            "request_id": request_id,
            "ok": True,
            "data": result,
        }
    except Exception as e:
        payload = {
            "request_id": request_id,
            "ok": False,
            "error": str(e),
        }

    # Même en cas d’erreur, on tente de notifier WXO
    try:
        await post_callback(callback_url, payload)
    except Exception:
        # Ici: log serveur (stdout, Sentry, etc.). On évite de lever une exception
        # car le traitement est "en arrière-plan".
        pass

@app.post("/edit-image") # Quand quelqu’un fait un POST sur /edit-image, utilise la fonction juste en dessous pour répondre.
async def edit_image(
    background_tasks: BackgroundTasks,
    callbackUrl: str = Header(..., description="WXO callback URL"), # Je veux lire un header HTTP nommé callbackUrl
    image: UploadFile = File(...), # Je m’attends à recevoir un fichier
    prompt: str = Form(...), # Je m’attends à recevoir un champ texte du formulaire
    # optionnel: si tu veux un champ supplémentaire
    #job_name: Optional[str] = Form(None),
):
    # 1) Lire immédiatement l’image (sinon l'objet UploadFile peut être fermé après la réponse)
    image_bytes = await image.read()

    # 2) Générer un ID (utile pour corréler la réponse callback)
    request_id = str(uuid.uuid4())

    # 3) Planifier le traitement en arrière-plan
    #    Note: BackgroundTasks exécute après avoir renvoyé la réponse HTTP.
    background_tasks.add_task(process_and_callback, callbackUrl, image_bytes, prompt, request_id)

    # 4) Répondre tout de suite en 202
    return JSONResponse(
        status_code=202,
        content={
            "accepted": True,
            "request_id": request_id,
            "message": "Traitement démarré, résultat envoyé via callbackUrl."
        },
    )