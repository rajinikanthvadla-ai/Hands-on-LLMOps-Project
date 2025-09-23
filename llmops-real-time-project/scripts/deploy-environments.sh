#!/bin/bash
set -e

# Deploy Kubernetes environments
# Usage: ./scripts/deploy-environments.sh [staging|production|both]

ENVIRONMENT=${1:-both}

echo "🚀 Deploying to: $ENVIRONMENT"

deploy_staging() {
    echo "📦 Deploying to staging..."
    kubectl apply -f k8s/staging/namespace.yaml
    kubectl apply -f k8s/staging/secrets.yaml
    kubectl apply -f k8s/staging/deployment.yaml
    kubectl apply -f k8s/staging/service.yaml
    
    echo "⏳ Waiting for staging deployment..."
    kubectl rollout status deployment/llmops-chatbot-deployment -n staging --timeout=300s
    
    echo "✅ Staging deployment complete"
}

deploy_production() {
    echo "📦 Deploying to production..."
    kubectl apply -f k8s/production/namespace.yaml
    kubectl apply -f k8s/production/secrets.yaml
    kubectl apply -f k8s/production/deployment.yaml
    kubectl apply -f k8s/production/service.yaml
    
    echo "⏳ Waiting for production deployment..."
    kubectl rollout status deployment/llmops-chatbot-deployment -n production --timeout=600s
    
    echo "✅ Production deployment complete"
}

case $ENVIRONMENT in
    staging)
        deploy_staging
        ;;
    production)
        deploy_production
        ;;
    both)
        deploy_staging
        deploy_production
        ;;
    *)
        echo "❌ Invalid environment: $ENVIRONMENT"
        echo "Usage: $0 [staging|production|both]"
        exit 1
        ;;
esac

echo "🎉 Deployment(s) completed successfully!"
