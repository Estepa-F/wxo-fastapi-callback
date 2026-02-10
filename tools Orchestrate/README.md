# Tools Orchestrate - watsonX Orchestrate Integration Guide

Mode d'emploi pour importer et utiliser les outils d'image processing dans IBM watsonX Orchestrate.

> **📚 Related Documentation:**
> Server API reference: [API.md](../API.md) · Setup: [README.md](../README.md) · Configuration: [CONFIGURATION.md](../CONFIGURATION.md) · Design: [ARCHITECTURE.md](../ARCHITECTURE.md)

---

## 📋 Vue d'ensemble

Ce dossier contient tous les fichiers nécessaires pour intégrer le service de traitement d'images dans watsonX Orchestrate :

- **3 API Tools (YAML)** - Endpoints asynchrones pour le traitement d'images
- **1 Python Tool** - Utilitaires de conversion Base64
- **3 Workflows (JSON)** - Flows prêts à l'emploi pour différents cas d'usage

---

## 🔧 API Tools (YAML)

### 1. `Async_Image_Processing_B64.yaml`

**Endpoint:** `/process-image-async-b64`  
**Opération:** `processImageAsyncToBase64`

**Ce qu'il fait:**  
Traite une image et retourne le résultat encodé en Base64 directement dans le callback.

**Inputs:**
- `prompt` (string, requis) - Instruction en langage naturel
- `image_base64` (string, requis) - Image source en Base64
- `filename` (string, optionnel) - Nom du fichier original

**Outputs (callback):**
- `status` - `completed` ou `failed`
- `job_id` - Identifiant unique du job
- `result_image_base64` - Image modifiée en Base64
- `result_mime_type` - Type MIME du résultat

**Cas d'usage:** Affichage direct dans le chat, prévisualisation rapide

---

### 2. `Async_Image_Processing_COS.yaml`

**Endpoint:** `/process-image-async`  
**Opération:** `processImageAsyncToCos`

**Ce qu'il fait:**  
Traite une image et stocke le résultat dans IBM Cloud Object Storage, retourne une URL pré-signée.

**Inputs:**
- `prompt` (string, requis) - Instruction en langage naturel
- `image_base64` (string, requis) - Image source en Base64
- `filename` (string, optionnel) - Nom du fichier original

**Outputs (callback):**
- `status` - `completed` ou `failed`
- `job_id` - Identifiant unique du job
- `result_url` - URL pré-signée vers l'image dans COS
- `expires_in` - Durée de validité de l'URL (secondes)

**Cas d'usage:** Stockage persistant, partage d'URL, intégration avec d'autres systèmes

---

### 3. `Async_Image_Batch_Process_COS.yaml`

**Endpoint:** `/batch-process-images`  
**Opération:** `batchProcessImages`

**Ce qu'il fait:**  
Traite toutes les images d'un bucket COS avec la même instruction, stocke les résultats dans un autre bucket.

**Inputs:**
- `prompt` (string, requis) - Instruction appliquée à toutes les images

**Outputs (callback):**
- `status` - `completed`, `completed_with_errors`, ou `failed`
- `job_id` - Identifiant unique du job
- `total_files` - Nombre total d'images trouvées
- `processed` - Nombre d'images traitées avec succès via OpenAI
- `fallback_local` - Nombre d'images traitées en fallback local
- `failed` - Nombre d'images en échec
- `duration_seconds` - Durée totale du traitement
- `output_bucket` - Bucket COS de destination
- `output_prefix` - Préfixe/dossier des résultats
- `errors` - Liste des erreurs rencontrées

**Cas d'usage:** Traitement en masse de catalogues, mise à jour de bibliothèques d'images

---

## 🐍 Python Tool

### `bytes_to_base64_min.py`

**Contient 2 outils:**

#### 1. `bytes_to_base64_minVersion`
- **Input:** `data` (bytes) - Données binaires
- **Output:** string - Chaîne Base64 encodée
- **Usage:** Convertir un fichier uploadé en Base64 avant envoi à l'API

#### 2. `base64_to_bytes_minVersion`
- **Input:** `data` (string) - Chaîne Base64 (sans préfixe `data:`)
- **Output:** bytes - Données binaires décodées
- **Usage:** Reconvertir un résultat Base64 en fichier téléchargeable

---

## 📊 Workflows (JSON)

### 1. `Modify_one_image_and_get_result.json`

**Nom d'affichage:** "Modify one image and get result"

**Ce qu'il fait:**  
Workflow interactif complet : upload image → traitement → affichage du résultat dans le chat

**Étapes:**
1. Formulaire utilisateur (upload image + prompt)
2. Conversion bytes → Base64
3. Extraction métadonnées
4. Appel API de traitement (Base64)
5. Récupération résultat
6. Conversion Base64 → bytes
7. Affichage image modifiée

**Output:** `image_output` (file) - Image modifiée téléchargeable

---

### 2. `Modify_one_image_and_save_result_COS.json`

**Nom d'affichage:** "Modify one image and save result"

**Ce qu'il fait:**  
Similaire au précédent, mais stocke le résultat dans COS et retourne une URL.

**Étapes:**
1. Formulaire utilisateur (upload image + prompt)
2. Conversion bytes → Base64
3. Extraction métadonnées
4. Appel API de traitement (COS)
5. Récupération URL
6. Affichage URL

**Output:** `URL_image` (string) - URL pré-signée vers l'image dans COS

---

### 3. `Modify_images_in_folder.json`

**Nom d'affichage:** "Modify images in folder and get result in another"

**Ce qu'il fait:**  
Traitement batch : applique une instruction à toutes les images d'un dossier COS.

**Input:** `Instructions` (string) - Prompt appliqué à toutes les images

**Outputs:**
- `status` - Statut final du batch
- `total_files_processed` - Nombre d'images traitées
- `duration` - Durée totale
- `output_bucket` - Bucket de destination
- `error` - Message d'erreur si échec

---

## 🚀 Import dans watsonX Orchestrate

### Prérequis

1. **Serveur FastAPI** accessible depuis WXO
   - Local: `http://host.lima.internal:8000` (voir [README.md](../README.md))
   - Production: URL publique avec HTTPS

2. **Variables d'environnement** configurées sur le serveur (voir [CONFIGURATION.md](../CONFIGURATION.md))

### Étapes d'import

#### 1. Importer les API Tools

1. Dans WXO, aller dans **Tools** → **Add Tool** → **OpenAPI**
2. Pour chaque fichier YAML :
   - Upload le fichier
   - Vérifier que l'URL du serveur est correcte (`http://host.lima.internal:8000` pour local)
   - Sauvegarder

#### 2. Importer le Python Tool

1. Dans WXO, aller dans **Tools** → **Add Tool** → **Python**
2. Upload `bytes_to_base64_min.py`
3. Les 2 fonctions seront automatiquement détectées
4. Sauvegarder

#### 3. Importer les Workflows

1. Dans WXO, aller dans **Flows** → **Import**
2. Pour chaque fichier JSON :
   - Upload le fichier
   - Vérifier les mappings de tools
   - Tester le workflow
   - Publier

---

## ⚙️ Configuration WXO

### Headers Requis

**IMPORTANT:** Le header `callbackUrl` est **case-sensitive**. Utilisez exactement :
```
callbackUrl: <url-fournie-par-wxo>
```

❌ Incorrect: `callbackurl`, `CallbackUrl`, `callback_url`  
✅ Correct: `callbackUrl`

### Callback Schema

WXO attend que le payload de callback corresponde **exactement** au schéma défini dans les YAML. Toute déviation causera une erreur.

### URL du Serveur

**Développement local (Lima VM):**
```yaml
servers:
  - url: http://host.lima.internal:8000
```

**Production:**
```yaml
servers:
  - url: https://your-domain.com
```

---

## 🧪 Test des Tools

### Test d'un API Tool

1. Dans WXO, ouvrir le tool
2. Cliquer sur **Test**
3. Fournir les inputs requis
4. Vérifier la réponse 202 Accepted
5. Attendre le callback avec les résultats

### Test d'un Workflow

1. Ouvrir le workflow
2. Cliquer sur **Run**
3. Suivre les étapes du formulaire
4. Vérifier les résultats

---

## 📝 Exemples de Prompts

### Pour une image unique
```
"Améliore la luminosité et les couleurs"
"Rends cette image plus professionnelle"
"Ajoute un effet vintage"
"Supprime l'arrière-plan"
```

### Pour un batch (restaurant)
```
"Améliore cette photo de nourriture pour qu'elle paraisse hautement appétissante, 
fraîche et professionnelle, comme une image utilisée sur Uber Eats. 
Accentue les couleurs naturelles, mets en valeur les textures, 
ajoute une lumière douce et chaleureuse."
```

---

## 🔍 Troubleshooting

### Tool ne se connecte pas au serveur

**Problème:** `Connection refused` ou timeout

**Solutions:**
- Vérifier que le serveur FastAPI tourne
- Pour local: vérifier que `host.lima.internal:8000` est accessible depuis la VM
- Pour production: vérifier l'URL et le certificat SSL

### Callback ne fonctionne pas

**Problème:** Le workflow reste bloqué après l'appel

**Solutions:**
- Vérifier que le header `callbackUrl` est bien fourni
- Vérifier que le payload de callback correspond au schéma YAML
- Consulter les logs du serveur FastAPI

### Erreur de conversion Base64

**Problème:** `ValueError: image_base64 invalide`

**Solutions:**
- Vérifier que l'image est bien encodée en Base64
- S'assurer qu'il n'y a pas de préfixe `data:image/...;base64,`
- Utiliser le tool `bytes_to_base64_minVersion` dans le workflow

---

## 📚 Documentation Complémentaire

- [README.md](../README.md) - Guide de démarrage rapide
- [API.md](../API.md) - Référence API complète
- [CONFIGURATION.md](../CONFIGURATION.md) - Variables d'environnement
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Architecture technique

---

**Version:** 1.0.0  
**Dernière mise à jour:** Février 2026