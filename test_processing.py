import asyncio

# ✅ Ta fonction (copie-colle)
async def do_image_processing(image_bytes: bytes, prompt: str) -> dict:
    return {
        "status": "success",
        "prompt_used": prompt,
        "result": {
            "message": "Traitement terminé",
            "image_size_bytes": len(image_bytes),
        }
    }

# ✅ Petit programme de test
async def main():
    # 1) On crée une "fausse image" (juste des bytes)
    fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"1234567890"  # signature PNG + contenu bidon

    # 2) On choisit un prompt
    prompt = "rends l'image plus lumineuse"

    # 3) On appelle la fonction (important: await)
    result = await do_image_processing(fake_image_bytes, prompt)

    # 4) On affiche le résultat
    print("Résultat retourné par la fonction :")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
