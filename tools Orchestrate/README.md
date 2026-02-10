# Tools Orchestrate - Documentation

Ce dossier contient les outils et workflows pour IBM watsonX Orchestrate permettant le traitement d'images via IA avec différents modes de fonctionnement.

## 📋 Vue d'ensemble

Les outils proposés permettent de :
- Traiter des images individuellement ou en masse
- Utiliser différents formats de sortie (Base64 ou Cloud Object Storage)
- Exécuter des traitements asynchrones avec callbacks
- Appliquer des transformations IA basées sur des prompts en langage naturel

---

## 🔧 Outils API (YAML)

### 1. `Async_Image_Processing_B64.yaml`

**Type** : API Tool (OpenAPI 3.0)  
**Endpoint** : `/process-image-async-b64`  
**Mode** : Asynchrone avec callback

**Description** :  
Traite une seule image de manière asynchrone et retourne le résultat encodé en Base64 via un callback.

**Paramètres d'entrée** :
- `prompt` (string, requis) : Instruction en langage naturel pour la transformation
- `image_base64` (string, requis) : Image source encodée en Base64
- `filename` (string, optionnel) : Nom du fichier original
- `callbackUrl` (header, requis) : URL de callback fournie par watsonX Orchestrate

**Réponse immédiate (202)** :
```json
{
  "accepted": true,
  "job_id": "uuid-du-job"
}
```

**Callback (POST vers callbackUrl)** :
```json
{
  "status": "completed",
  "job_id": "uuid-du-job",
  "filename": "image.jpg",
  "result_image_base64": "base64-encoded-result"
}
```

**Cas d'usage** :  
Idéal pour traiter une image et récupérer directement le résultat dans le workflow sans passer par un stockage externe.

---

### 2. `Async_Image_Processing_COS.yaml`

**Type** : API Tool (OpenAPI 3.0)  
**Endpoint** : `/process-image-async`  
**Mode** : Asynchrone avec callback

**Description** :  
Traite une seule image de manière asynchrone et stocke le résultat dans IBM Cloud Object Storage (COS). Retourne une URL pré-signée temporaire.

**Paramètres d'entrée** :
- `prompt` (string, requis) : Instruction en langage naturel
- `image_base64` (string, requis) : Image source en Base64
- `filename` (string, optionnel) : Nom du fichier
- `callbackUrl` (header, requis) : URL de callback

**Réponse immédiate (202)** :
```json
{
  "accepted": true,
  "job_id": "uuid-du-job"
}
```

**Callback (POST vers callbackUrl)** :
```json
{
  "status": "completed",
  "job_id": "uuid-du-job",
  "filename": "image.jpg",
  "result_url": "https://cos-url/result.jpg",
  "expires_in": 3600
}
```

**Cas d'usage** :  
Préférable pour les images volumineuses ou lorsque vous souhaitez conserver les résultats dans un stockage cloud avec accès via URL.

---

### 3. `Async_Image_Batch_Process_COS.yaml`

**Type** : API Tool (OpenAPI 3.0)  
**Endpoint** : `/batch-process-images`  
**Mode** : Asynchrone avec callback

**Description** :  
Traite en masse toutes les images d'un bucket/préfixe COS et stocke les résultats dans un autre bucket/préfixe. Applique la même transformation à toutes les images.

**Paramètres d'entrée** :
- `prompt` (string, requis) : Instruction appliquée à toutes les images
- `callbackUrl` (header, requis) : URL de callback

**Configuration COS** :  
Les buckets d'entrée/sortie sont configurés dans les variables d'environnement du serveur FastAPI.

**Réponse immédiate (202)** :
```json
{
  "accepted": true,
  "job_id": "uuid-du-job"
}
```

**Callback (POST vers callbackUrl)** :
```json
{
  "status": "completed",
  "job_id": "uuid-du-job",
  "total_files": 50,
  "total_files_processed": 50,
  "processed": 48,
  "failed": 2,
  "fallback_local": 0,
  "duration_seconds": 245.3,
  "output_bucket": "output-bucket",
  "output_prefix": "results/job-uuid/",
  "errors": ["Error processing image1.jpg: timeout"]
}
```

**Cas d'usage** :  
Parfait pour traiter automatiquement un catalogue complet d'images (ex: améliorer toutes les photos d'un menu restaurant).

---

## 🐍 Utilitaires Python

### 4. `bytes_to_base64_min.py`

**Type** : Python Tools pour watsonX Orchestrate  
**Fonctions** : 2 outils de conversion

#### Tool 1 : `bytes_to_base64_minVersion`

**Description** : Convertit des bytes bruts en chaîne Base64

**Paramètres** :
- `data` (bytes) : Données binaires à encoder

**Retour** :
- `string` : Chaîne Base64 encodée (ASCII)

**Permission** : READ_ONLY

#### Tool 2 : `base64_to_bytes_minVersion`

**Description** : Convertit une chaîne Base64 en bytes bruts

**Paramètres** :
- `data` (string) : Chaîne Base64 (sans préfixe `data:`)

**Retour** :
- `bytes` : Données binaires décodées

**Permission** : READ_ONLY

**Cas d'usage** :  
Ces outils sont utilisés dans les workflows pour convertir les fichiers uploadés par l'utilisateur en Base64 avant envoi à l'API, et reconvertir les résultats Base64 en fichiers téléchargeables.

---

## 📊 Workflows watsonX Orchestrate (JSON)

### 5. `Modify_one_image_and_get_result.json`

**Type** : Workflow interactif  
**Nom d'affichage** : "Modify one image and get result"

**Description** :  
Workflow complet permettant à l'utilisateur d'uploader une image, de fournir un prompt, et de recevoir directement le résultat modifié dans le chat.

**Étapes du workflow** :
1. **User Activity** : Formulaire avec 2 champs
   - Upload d'image (JPEG, JPG, PNG, max 10MB)
   - Champ texte pour le prompt
2. **Convert bytes to base64** : Conversion de l'image uploadée
3. **Get infos image** : Extraction du nom et du contenu Base64
4. **Process image async (B64)** : Appel de l'API de traitement
5. **Recup result** : Extraction du résultat Base64
6. **Convert base64 to bytes** : Reconversion en fichier
7. **Output** : Affichage de l'image modifiée

**Sortie** :
- `image_output` (file) : Image modifiée téléchargeable

**Cas d'usage** :  
Expérience utilisateur simple et rapide pour tester des modifications d'images individuelles.

---

### 6. `Modify_one_image_and_save_result_COS.json`

**Type** : Workflow interactif  
**Nom d'affichage** : "Modify one image and save result"

**Description** :  
Similaire au workflow précédent, mais stocke le résultat dans IBM Cloud Object Storage et retourne une URL d'accès sécurisée.

**Étapes du workflow** :
1. **User Activity** : Upload image + prompt
2. **Convert bytes to base64** : Conversion
3. **Get infos image** : Extraction des métadonnées
4. **Process image async (COS)** : Appel API avec stockage COS
5. **Recup result** : Extraction de l'URL
6. **Output** : URL du résultat

**Sortie** :
- `URL_image` (string) : URL pré-signée vers l'image stockée dans COS

**Cas d'usage** :  
Préférable pour les images volumineuses ou lorsque vous souhaitez partager l'URL du résultat avec d'autres systèmes.

---

### 7. `Modify_images_in_folder.json`

**Type** : Workflow batch  
**Nom d'affichage** : "Modify images in folder and get result in another"

**Description** :  
Workflow de traitement en masse permettant d'appliquer une transformation IA à toutes les images d'un dossier COS.

**Paramètres d'entrée** :
- `Instructions` (string, requis) : Prompt appliqué à toutes les images
  - Exemple par défaut : Amélioration de photos de nourriture pour Uber Eats

**Étapes du workflow** :
1. **Input** : Réception du prompt utilisateur
2. **Batch Process Images** : Appel de l'API batch
3. **Output** : Statistiques du traitement

**Sortie** :
- `status` (string) : Statut final (completed, completed_with_errors, failed)
- `total_files_processed` (integer) : Nombre d'images traitées
- `duration` (number) : Durée totale en secondes
- `output_bucket` (string) : Bucket COS de destination
- `error` (string) : Message d'erreur si échec

**Cas d'usage** :  
Traitement automatisé de catalogues complets (ex: améliorer 100 photos de menu restaurant en une seule opération).

---

## 🚀 Configuration requise

### Variables d'environnement (serveur FastAPI)

```bash
# IBM Cloud Object Storage
COS_ENDPOINT=https://s3.eu-de.cloud-object-storage.appdomain.cloud
COS_API_KEY_ID=your-api-key
COS_INSTANCE_CRN=your-instance-crn
COS_INPUT_BUCKET=input-bucket-name
COS_OUTPUT_BUCKET=output-bucket-name

# OpenAI (ou autre service IA)
OPENAI_API_KEY=your-openai-key
```

### Prérequis watsonX Orchestrate

- Compte IBM watsonX Orchestrate actif
- Accès à IBM Cloud Object Storage (pour les workflows COS)
- Serveur FastAPI déployé et accessible depuis watsonX Orchestrate
- Tools Python déployés dans l'environnement watsonX

---

## 📝 Exemples de prompts

### Pour une image unique
```
"Améliore la luminosité et les couleurs de cette photo"
"Rends cette image plus professionnelle"
"Ajoute un effet vintage à cette photo"
```

### Pour un batch d'images (restaurant)
```
"Améliore cette photo de nourriture pour qu'elle paraisse hautement appétissante, 
fraîche et professionnelle, comme une image utilisée sur Uber Eats. 
Accentue les couleurs naturelles, mets en valeur les textures, 
ajoute une lumière douce et chaleureuse."
```

---

## 🔗 Architecture

```
User (watsonX Orchestrate)
    ↓
Workflow JSON
    ↓
Python Tools (conversion Base64)
    ↓
API YAML (FastAPI server)
    ↓
IA Processing (OpenAI/autre)
    ↓
IBM Cloud Object Storage (optionnel)
    ↓
Callback → watsonX Orchestrate
    ↓
Result to User
```

---

## 📚 Documentation complémentaire

- [API.md](../API.md) : Documentation détaillée de l'API FastAPI
- [ARCHITECTURE.md](../ARCHITECTURE.md) : Architecture technique du système
- [README.md](../README.md) : Guide d'installation et de démarrage

---

## 🆘 Support

Pour toute question ou problème :
1. Vérifiez que le serveur FastAPI est accessible
2. Vérifiez les variables d'environnement COS
3. Consultez les logs du serveur FastAPI
4. Vérifiez les permissions watsonX Orchestrate

---

**Version** : 1.0.0  
**Dernière mise à jour** : Février 2026