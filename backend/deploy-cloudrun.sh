#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# deploy-cloudrun.sh — Deploy 3ioNetra backend to Google Cloud Run
#
# Prerequisites:
#   1. gcloud CLI installed & authenticated (gcloud auth login)
#   2. A GCP project selected (gcloud config set project <PROJECT_ID>)
#   3. Artifact Registry repo created (or use --source for Cloud Build)
#   4. Secret Manager API enabled (gcloud services enable secretmanager.googleapis.com)
#   5. Cloud Run API enabled   (gcloud services enable run.googleapis.com)
#
# Usage:
#   ./deploy-cloudrun.sh                  # interactive — prompts for secrets
#   ./deploy-cloudrun.sh --skip-secrets   # skip Secret Manager setup
# ---------------------------------------------------------------------------
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────
SERVICE_NAME="3ionetra-backend"
REGION="asia-south1"
MEMORY="2Gi"
CPU="2"
MIN_INSTANCES=0
MAX_INSTANCES=4
TIMEOUT="300"
CONCURRENCY=80

# ── Parse flags ────────────────────────────────────────────────────────────
SKIP_SECRETS=false
for arg in "$@"; do
  case $arg in
    --skip-secrets) SKIP_SECRETS=true ;;
  esac
done

# ── Helpers ────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m[INFO]\033[0m  %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m  %s\n' "$*"; }
error() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*"; exit 1; }

PROJECT_ID=$(gcloud config get-value project 2>/dev/null) || error "No GCP project set. Run: gcloud config set project <PROJECT_ID>"
info "Project: $PROJECT_ID | Region: $REGION | Service: $SERVICE_NAME"

# ── Step 1: Create / update secrets in Secret Manager ──────────────────────
create_or_update_secret() {
  local name=$1 value=$2
  if gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- --project="$PROJECT_ID" --quiet
    info "Updated secret: $name"
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --replication-policy="automatic" --project="$PROJECT_ID" --quiet
    info "Created secret: $name"
  fi
}

if [ "$SKIP_SECRETS" = false ]; then
  info "Setting up Secret Manager secrets..."
  echo ""
  echo "Enter values for the 4 sensitive secrets (leave blank to skip):"
  echo ""

  read -rsp "GEMINI_API_KEY: " GEMINI_API_KEY; echo ""
  read -rsp "MONGODB_URI: " MONGODB_URI; echo ""
  read -rsp "DATABASE_PASSWORD: " DATABASE_PASSWORD; echo ""
  read -rsp "REDIS_PASSWORD: " REDIS_PASSWORD; echo ""

  [ -n "$GEMINI_API_KEY" ]    && create_or_update_secret "GEMINI_API_KEY" "$GEMINI_API_KEY"
  [ -n "$MONGODB_URI" ]       && create_or_update_secret "MONGODB_URI" "$MONGODB_URI"
  [ -n "$DATABASE_PASSWORD" ] && create_or_update_secret "DATABASE_PASSWORD" "$DATABASE_PASSWORD"
  [ -n "$REDIS_PASSWORD" ]    && create_or_update_secret "REDIS_PASSWORD" "$REDIS_PASSWORD"

  echo ""
  info "Granting Cloud Run service account access to secrets..."
  SA="${PROJECT_ID}@appspot.gserviceaccount.com"
  for secret in GEMINI_API_KEY MONGODB_URI DATABASE_PASSWORD REDIS_PASSWORD; do
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" &>/dev/null; then
      gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:${SA}" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" --quiet 2>/dev/null || true
    fi
  done
fi

# ── Step 2: Build & deploy to Cloud Run ────────────────────────────────────
info "Deploying to Cloud Run from source..."

# Non-sensitive env vars (no LOG_FILE — Cloud Run uses stdout → Cloud Logging)
ENV_VARS="DEBUG=false"
ENV_VARS+=",API_HOST=0.0.0.0"
ENV_VARS+=",API_PORT=8080"
ENV_VARS+=",LOG_LEVEL=INFO"
ENV_VARS+=",RETRIEVAL_TOP_K=7"
ENV_VARS+=",RERANK_TOP_K=3"
ENV_VARS+=",MIN_SIMILARITY_SCORE=0.15"
ENV_VARS+=",ENABLE_CRISIS_DETECTION=true"
ENV_VARS+=",CRISIS_HELPLINE_IN=iCall: 9152987821, Vandrevala: 1860-2662-345"
ENV_VARS+=",SESSION_TTL_MINUTES=60"
ENV_VARS+=",DATABASE_NAME=spiritual_voice_bot"
ENV_VARS+=",REDIS_HOST=redis-11574.c330.asia-south1-1.gce.cloud.redislabs.com"
ENV_VARS+=",REDIS_PORT=11574"
ENV_VARS+=",REDIS_DB=0"
ENV_VARS+=",ALLOWED_ORIGINS=https://3iomitra.3iosetu.com,https://3io-netra.vercel.app"

# Secret references (env var name=SECRET_NAME:version)
SECRETS="GEMINI_API_KEY=GEMINI_API_KEY:latest"
SECRETS+=",MONGODB_URI=MONGODB_URI:latest"
SECRETS+=",DATABASE_PASSWORD=DATABASE_PASSWORD:latest"
SECRETS+=",REDIS_PASSWORD=REDIS_PASSWORD:latest"

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --timeout "$TIMEOUT" \
  --concurrency "$CONCURRENCY" \
  --port 8080 \
  --set-env-vars "$ENV_VARS" \
  --set-secrets "$SECRETS" \
  --allow-unauthenticated \
  --quiet

# ── Step 3: Verify ─────────────────────────────────────────────────────────
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)' 2>/dev/null)
info "Deployed! Service URL: $SERVICE_URL"
info "Health check: curl ${SERVICE_URL}/api/health"
echo ""
info "To view logs: gcloud run logs read --service=$SERVICE_NAME --region=$REGION --limit=50"
