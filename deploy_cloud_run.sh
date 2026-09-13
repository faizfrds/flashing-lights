#!/bin/bash
set -e

PROJECT_ID=${1:-"flashflood-508519"}
REGION=${2:-"asia-southeast2"}
SERVICE_NAME="ffews-sentinel"

echo "========================================================"
echo " 🌊 Deploying Indonesia FFEWS to Google Cloud Run"
echo " Project: $PROJECT_ID | Region: $REGION"
echo "========================================================"

# 1. Enable required Google Cloud APIs
echo "Enabling Cloud Run, Cloud Build, Artifact Registry, and Cloud Scheduler APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  earthengine.googleapis.com \
  --project="$PROJECT_ID"

# 2. Grant Earth Engine permissions to the default Compute / Cloud Run service account
echo "Configuring Earth Engine IAM permissions for Cloud Run service account..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
DEFAULT_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Granting Earth Engine access to $DEFAULT_SA..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$DEFAULT_SA" \
  --role="roles/earthengine.writer" \
  --quiet 2>/dev/null || true

# 3. Read environment variables from .env
ENV_FLAG="--set-env-vars=GEE_PROJECT_ID=$PROJECT_ID,DEFAULT_REGION=west_java"

if [ -f .env ]; then
  echo "Loading webhook and threshold variables from .env..."
  while IFS= read -r line || [ -n "$line" ]; do
    # Remove leading/trailing whitespace
    line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    # Ignore comments and empty lines
    if [[ ! -z "$line" && ! "$line" =~ ^# && "$line" =~ = ]]; then
      key=$(echo "$line" | cut -d '=' -f 1)
      val=$(echo "$line" | cut -d '=' -f 2-)
      # Skip empty values and GEE_SERVICE_ACCOUNT_KEY (Cloud Run uses native IAM)
      if [[ ! -z "$val" && "$key" != "GEE_SERVICE_ACCOUNT_KEY" ]]; then
        ENV_FLAG="$ENV_FLAG,$key=$val"
      fi
    fi
  done < .env
fi

# 4. Build and deploy container to Cloud Run
echo "Building container image and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --allow-unauthenticated \
  $ENV_FLAG \
  --memory 1Gi \
  --cpu 1 \
  --timeout 600

# 5. Retrieve Cloud Run Service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)')
echo "Service successfully deployed at: $SERVICE_URL"

# 6. Configure Cloud Scheduler to trigger /trigger every 3 hours
JOB_NAME="ffews-3hour-trigger"
echo "Configuring Cloud Scheduler job '$JOB_NAME'..."

# Delete old job if it already exists
gcloud scheduler jobs delete "$JOB_NAME" --location="$REGION" --project="$PROJECT_ID" --quiet 2>/dev/null || true

gcloud scheduler jobs create http "$JOB_NAME" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --schedule="0 */3 * * *" \
  --uri="$SERVICE_URL/trigger" \
  --http-method=POST \
  --time-zone="Asia/Jakarta" \
  --attempt-deadline="10m"

echo "========================================================"
echo " ✅ Deployment Complete!"
echo " 🌐 Live Web Dashboard : $SERVICE_URL/map"
echo " 🛰️ Live GeoJSON Feed  : $SERVICE_URL/alerts.geojson"
echo " ⏰ Automated Trigger   : $SERVICE_URL/trigger"
echo " 📅 Schedule            : Every 3 hours (Asia/Jakarta)"
echo "========================================================"
