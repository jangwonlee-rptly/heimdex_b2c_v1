#!/bin/bash
# Heimdex B2C - GCP Deployment Script
# This script helps deploy to Google Cloud Platform

set -e

echo "=========================================="
echo "Heimdex B2C - GCP Deployment"
echo "=========================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "   Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: Terraform is not installed"
    echo "   Install from: https://www.terraform.io/downloads"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Prompt for environment
echo "Select deployment environment:"
echo "  1) dev-gcp (Development)"
echo "  2) prod (Production)"
read -p "Enter choice [1-2]: " env_choice

case $env_choice in
    1)
        ENV="dev-gcp"
        ;;
    2)
        ENV="prod"
        echo "⚠️  WARNING: You are deploying to PRODUCTION"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            echo "Deployment cancelled"
            exit 0
        fi
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Deploying to: $ENV"
echo ""

# Check if user is authenticated
echo "🔐 Checking GCP authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q @; then
    echo "❌ Not authenticated with GCP"
    echo "   Run: gcloud auth login"
    exit 1
fi

ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1)
echo "✅ Authenticated as: $ACCOUNT"
echo ""

# Prompt for project ID
read -p "Enter GCP Project ID: " PROJECT_ID
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Project ID is required"
    exit 1
fi

echo "Setting project: $PROJECT_ID"
gcloud config set project $PROJECT_ID

echo ""
echo "📦 Step 1: Build and push Docker images to Artifact Registry"
echo ""

# Configure Docker for Artifact Registry
REGION="us-central1"
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push API
echo "Building API image..."
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/heimdex/api:latest ./api
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/heimdex/api:latest

# Build and push Worker
echo "Building Worker image..."
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/heimdex/worker:latest ./worker
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/heimdex/worker:latest

echo "✅ Images pushed to Artifact Registry"
echo ""

echo "🏗️  Step 2: Deploy infrastructure with Terraform"
echo ""

cd infra/envs/$ENV

# Initialize Terraform (if not already initialized)
if [ ! -d ".terraform" ]; then
    echo "Initializing Terraform..."
    terraform init
fi

# Plan
echo "Creating Terraform plan..."
terraform plan -out=tfplan

# Confirm
echo ""
read -p "Review the plan above. Apply changes? (yes/no): " apply_confirm
if [ "$apply_confirm" != "yes" ]; then
    echo "Deployment cancelled"
    exit 0
fi

# Apply
echo "Applying Terraform changes..."
terraform apply tfplan

echo "✅ Infrastructure deployed"
echo ""

echo "🚀 Step 3: Deploy Cloud Run services"
echo ""

# Get outputs from Terraform
DB_CONNECTION=$(terraform output -raw cloud_sql_connection_name)
REDIS_HOST=$(terraform output -raw redis_host)
GCS_BUCKET=$(terraform output -raw gcs_bucket_uploads)

echo "Deploying API service..."
gcloud run deploy heimdex-api \
    --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/heimdex/api:latest \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars "POSTGRES_HOST=${DB_CONNECTION}" \
    --set-env-vars "REDIS_HOST=${REDIS_HOST}" \
    --set-env-vars "STORAGE_BACKEND=gcs" \
    --set-env-vars "GCS_BUCKET_UPLOADS=${GCS_BUCKET}" \
    --set-secrets "JWT_SECRET_KEY=jwt-secret:latest" \
    --set-secrets "POSTGRES_PASSWORD=db-password:latest" \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --concurrency 80

echo "Deploying Worker service..."
gcloud run deploy heimdex-worker \
    --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/heimdex/worker:latest \
    --region ${REGION} \
    --platform managed \
    --no-allow-unauthenticated \
    --set-env-vars "POSTGRES_HOST=${DB_CONNECTION}" \
    --set-env-vars "REDIS_HOST=${REDIS_HOST}" \
    --set-env-vars "STORAGE_BACKEND=gcs" \
    --set-env-vars "GCS_BUCKET_UPLOADS=${GCS_BUCKET}" \
    --set-secrets "POSTGRES_PASSWORD=db-password:latest" \
    --memory 8Gi \
    --cpu 4 \
    --max-instances 5

echo "✅ Services deployed"
echo ""

echo "=========================================="
echo "🎉 Deployment Complete!"
echo "=========================================="
echo ""

# Get service URLs
API_URL=$(gcloud run services describe heimdex-api --region ${REGION} --format="value(status.url)")

echo "Services:"
echo "  API: ${API_URL}"
echo "  API Health: ${API_URL}/health"
echo "  API Docs: ${API_URL}/docs"
echo ""
echo "Next steps:"
echo "  1. Test API: curl ${API_URL}/health"
echo "  2. Set up monitoring alerts in Cloud Console"
echo "  3. Configure custom domain (if needed)"
echo "  4. Run integration tests"
echo ""
echo "To view logs:"
echo "  gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=heimdex-api' --limit 50"
echo ""
echo "To rollback (if needed):"
echo "  gcloud run services update-traffic heimdex-api --to-revisions PREVIOUS_REVISION=100"
echo ""

# Return to original directory
cd ../../..

echo "Deployment log saved to: infra/envs/$ENV/deployment.log"
echo ""
echo "Happy deploying! 🚀"
