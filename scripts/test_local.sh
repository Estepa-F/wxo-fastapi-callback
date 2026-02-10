#!/usr/bin/env bash
set -euo pipefail

echo "==============================================="
echo "🧪 WXO FastAPI – Local Integration Test Script"
echo "==============================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="http://localhost:8000"
CALLBACK_PORT=9999
CALLBACK_URL="http://localhost:${CALLBACK_PORT}/callback"

echo ""
echo "📂 Project root: $ROOT_DIR"

# ------------------------------------------------
# 1. Check environment
# ------------------------------------------------
echo ""
echo "🔎 Checking environment variables..."

REQUIRED_VARS=(
  COS_ENDPOINT
  COS_REGION
  COS_ACCESS_KEY_ID
  COS_SECRET_ACCESS_KEY
  COS_INPUT_BUCKET
  COS_OUTPUT_BUCKET
  OPENAI_API_KEY
)

MISSING=false
for VAR in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!VAR:-}" ]]; then
    echo "❌ Missing env var: $VAR"
    MISSING=true
  else
    echo "✅ $VAR"
  fi
done

if [[ "$MISSING" == "true" ]]; then
  echo ""
  echo "❌ Environment not correctly configured."
  echo "👉 Did you run: set -a && source .env && set +a ?"
  exit 1
fi

# ------------------------------------------------
# 2. Health check
# ------------------------------------------------
echo ""
echo "🏥 Health check..."

if ! curl -sf "${API_URL}/health" > /dev/null; then
  echo "❌ FastAPI server not reachable at ${API_URL}"
  echo "👉 Is uvicorn running?"
  exit 1
fi

echo "✅ FastAPI server is healthy"

# ------------------------------------------------
# 3. COS configuration check
# ------------------------------------------------
echo ""
echo "🪣 Checking COS configuration..."

curl -sf "${API_URL}/cos/config" | jq .

# ------------------------------------------------
# 4. Start callback server
# ------------------------------------------------
echo ""
echo "📡 Starting local callback server on port ${CALLBACK_PORT}..."

CALLBACK_LOG="$(mktemp)"
python - <<'PY' > "$CALLBACK_LOG" 2>&1 &
from fastapi import FastAPI
import uvicorn
from datetime import datetime, timezone

app = FastAPI()

@app.post("/callback")
def cb(data: dict):
    print(f"\n--- {datetime.now(timezone.utc).isoformat()} ---")
    print(data)
    return {"ok": True}

uvicorn.run(app, host="127.0.0.1", port=9999)
PY

CALLBACK_PID=$!
sleep 2

echo "✅ Callback server started (PID: $CALLBACK_PID)"

cleanup() {
  echo ""
  echo "🧹 Cleaning up callback server..."
  kill "$CALLBACK_PID" 2>/dev/null || true
}
trap cleanup EXIT

# ------------------------------------------------
# 5. Single image test (Base64)
# ------------------------------------------------
echo ""
echo "🖼️ Testing single image processing (Base64)..."

TEST_IMAGE="$ROOT_DIR/burger.jpeg"
if [[ ! -f "$TEST_IMAGE" ]]; then
  echo "❌ Test image not found: burger.jpeg"
  exit 1
fi

B64=$(base64 -i "$TEST_IMAGE" | tr -d '\n')

curl -s -X POST "${API_URL}/process-image-async-b64" \
  -H "Content-Type: application/json" \
  -H "callbackUrl: ${CALLBACK_URL}" \
  -d "{
    \"prompt\": \"add a dog\",
    \"filename\": \"burger.jpeg\",
    \"image_base64\": \"${B64}\"
  }" | jq .

echo "⏳ Waiting for callback..."
sleep 5
cat "$CALLBACK_LOG"

# ------------------------------------------------
# 6. Batch processing test
# ------------------------------------------------
echo ""
echo "📦 Testing batch image processing..."

curl -s -X POST "${API_URL}/batch-process-images" \
  -H "Content-Type: application/json" \
  -H "callbackUrl: ${CALLBACK_URL}" \
  -d '{"prompt":"make the image more beautiful"}' | jq .

echo "⏳ Waiting for batch callback..."
sleep 8
cat "$CALLBACK_LOG"

echo ""
echo "==============================================="
echo "✅ All local tests completed successfully"
echo "==============================================="
