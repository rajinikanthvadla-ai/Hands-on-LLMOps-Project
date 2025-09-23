# LLMOps Real-Time Project - Complete Deployment Guide

## 🎯 Overview
This guide walks you through setting up a production-ready LLM chatbot with complete MLOps lifecycle: AWS infrastructure, containerized FastAPI app, Kubernetes deployment, monitoring, and CI/CD automation.

## 📋 Prerequisites
- AWS Account with billing enabled
- GitHub Account
- Local tools: AWS CLI, Docker Desktop, kubectl, git
- Hugging Face account (free)

---

## 🏗️ Phase 1: AWS Infrastructure Setup (15-20 mins)

### Step 1.1: Create IAM User
```bash
# In AWS Console:
# 1. Go to IAM → Users → Create user
# 2. Name: llmops-project-user
# 3. Check: Programmatic access + AWS Management Console access
# 4. Attach policy: AdministratorAccess
# 5. ✅ SAVE Access Key ID and Secret Access Key
```

### Step 1.2: Configure AWS CLI
```bash
aws configure
# AWS Access Key ID: [your key]
# AWS Secret Access Key: [your secret]
# Default region: us-east-1
# Default output: json

# Verify
aws sts get-caller-identity
```

### Step 1.3: Create S3 Bucket
```bash
aws s3 mb s3://llmops-knowledge-base --region us-east-1
```

### Step 1.4: Create ECR Repository
```bash
aws ecr create-repository --repository-name llmops-real-time-chatbot --region us-east-1
# ✅ Save the repositoryUri from output (e.g., 123456789012.dkr.ecr.us-east-1.amazonaws.com/llmops-real-time-chatbot)
```

### Step 1.5: Create DynamoDB Table
```bash
aws dynamodb create-table \
  --table-name llmops-feedback-log \
  --attribute-definitions AttributeName=feedback_id,AttributeType=S \
  --key-schema AttributeName=feedback_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

### Step 1.6: Create EKS Cluster (15-20 minutes)
```bash
# Install eksctl if not installed
# Windows: choco install eksctl
# macOS: brew install eksctl

eksctl create cluster \
  --name llmops-production-cluster \
  --region us-east-1 \
  --nodegroup-name llm-workers \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 4

# Verify
kubectl get nodes
```

---

## 🔧 Phase 2: Local Development Setup

### Step 2.1: Get Hugging Face Token
1. Go to https://huggingface.co/settings/tokens
2. Create new token with read permissions
3. ✅ Save token: `hf_xxxxxxxxxxxxxxxxxxxxxxxx`

### Step 2.2: Clone/Setup Project
```bash
# If you haven't cloned yet:
git clone <your-repo-url>
cd llmops-real-time-project

# Or if you're already in the project:
# You should see: data_pipeline/, model_service/, k8s/, .github/workflows/
```

### Step 2.3: Build Knowledge Base (Run Data Pipeline)
```powershell
# Windows PowerShell
cd llmops-real-time-project

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r model_service\requirements.txt
python -m pip install pandas

# Set environment variables
$env:S3_BUCKET_NAME = "llmops-knowledge-base"
$env:S3_FAISS_PREFIX = "faiss_index"

# Run data pipeline
python data_pipeline\process_data.py

# Should output:
# 🔧 Initializing embedding model...
# 📚 Loading data...
# 🔄 Creating FAISS vector index...
# ☁️ Uploading index to S3...
# ✅ Data pipeline complete!
```

### Step 2.4: Verify S3 Upload
```bash
aws s3 ls s3://llmops-knowledge-base/faiss_index/
# Should show: index.faiss, index.pkl files
```

---

## 🐳 Phase 3: Container & Kubernetes Deployment

### Step 3.1: Update Kubernetes Secrets
Edit `k8s/secrets.yaml` with your actual values:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: chatbot-secrets
type: Opaque
stringData:
  S3_BUCKET_NAME: "llmops-knowledge-base"
  S3_FAISS_PREFIX: "faiss_index"
  HUGGINGFACEHUB_API_TOKEN: "hf_your_actual_token_here"
  DYNAMODB_FEEDBACK_TABLE: "llmops-feedback-log"
```

### Step 3.2: Update Deployment Image
Edit `k8s/deployment.yaml` line 19:
```yaml
          image: YOUR_ECR_URI:v1.0  # Replace with actual ECR URI
```

### Step 3.3: Build and Push Docker Image
```bash
cd model_service

# Build image
docker build -t llmops-real-time-chatbot:v1.0 .

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URI

# Tag and push (replace YOUR_ECR_URI with actual value)
docker tag llmops-real-time-chatbot:v1.0 YOUR_ECR_URI:v1.0
docker push YOUR_ECR_URI:v1.0
```

### Step 3.4: Deploy to Kubernetes
```bash
cd ../k8s

# Apply secrets
kubectl apply -f secrets.yaml

# Apply deployment and service
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# Monitor deployment
kubectl get pods -w
# Wait for pods to be Running

# Get service URL
kubectl get service llmops-chatbot-service
# Note the EXTERNAL-IP
```

### Step 3.5: Test Live Service
```bash
export CHATBOT_URL="http://YOUR_EXTERNAL_IP"

# Test health endpoint
curl $CHATBOT_URL/health

# Test chat endpoint
curl -X POST "$CHATBOT_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I fix a slow laptop?"}'

# Test feedback endpoint
curl -X POST "$CHATBOT_URL/feedback" \
  -H "Content-Type: application/json" \
  -d '{"query_id": "test-123", "query": "test question", "answer": "test answer", "is_correct": true}'
```

---

## 📊 Phase 4: Monitoring Setup

### Step 4.1: Install Prometheus & Grafana
```bash
# Add Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install monitoring stack
helm install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace
```

### Step 4.2: Access Grafana
```bash
# Port forward Grafana
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80

# Get admin password
kubectl -n monitoring get secret monitoring-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode
```

Open http://localhost:3000 (admin / [password from above])

### Step 4.3: Create LLMOps Dashboard
1. **Add Data Source**: Prometheus (http://monitoring-prometheus-server:9090)
2. **Create Dashboard** with panels:
   - **Requests/min**: `sum(rate(fastapi_requests_total[2m])) * 60`
   - **P95 Latency**: `histogram_quantile(0.95, sum(rate(fastapi_request_duration_seconds_bucket[5m])) by (le))`
   - **Token Throughput**: `sum(rate(chatbot_prompt_tokens_total[5m]))`

---

## 🚀 Phase 5: GitHub Actions CI/CD Setup

### Step 5.1: Push to GitHub
```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "feat: Initial LLMOps chatbot implementation"
git branch -M main

# Add remote and push
git remote add origin https://github.com/yourusername/llmops-real-time-project.git
git push -u origin main
```

### Step 5.2: Configure GitHub Secrets
In your GitHub repository, go to **Settings → Secrets and Variables → Actions** and add:

| Secret Name | Value | Example |
|-------------|--------|---------|
| `AWS_ACCESS_KEY_ID` | Your IAM user access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Your IAM user secret key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `ECR_REPOSITORY_URI` | ECR repository URI | `123456789012.dkr.ecr.us-east-1.amazonaws.com/llmops-real-time-chatbot` |
| `EKS_CLUSTER_NAME` | EKS cluster name | `llmops-production-cluster` |
| `S3_BUCKET_NAME` | S3 bucket name | `llmops-knowledge-base` |
| `HUGGINGFACEHUB_API_TOKEN` | Hugging Face token | `hf_xxxxxxxxxxxxxxxxxxxxxxxx` |
| `DYNAMODB_FEEDBACK_TABLE` | DynamoDB table name | `llmops-feedback-log` |

### Step 5.3: Setup GitHub Environments (Manual Approval)
1. Go to **Settings → Environments**
2. Create environment: `staging`
3. Create environment: `production`
   - ✅ Check "Required reviewers"
   - Add yourself as a reviewer
   - Set wait timer: 5 minutes (optional)

### Step 5.4: Deploy Environment Infrastructure
```bash
# Deploy both staging and production namespaces
./scripts/deploy-environments.sh both

# Or deploy individually:
# ./scripts/deploy-environments.sh staging
# ./scripts/deploy-environments.sh production
```

### Step 5.5: Test CI/CD Pipeline

**Automatic Deployment (develop branch → staging):**
```bash
git checkout -b develop
echo "# Test staging" >> README.md
git add README.md
git commit -m "test: Trigger staging deployment"
git push origin develop
```

**Manual Deployment (GitHub UI):**
1. Go to **Actions** tab
2. Click "LLMOps CI/CD Pipeline"
3. Click "Run workflow"
4. Select environment: `staging` or `production`
5. Click "Run workflow"

**Production Deployment (main branch):**
```bash
git checkout main
git merge develop
git push origin main
# ⚠️ This will require manual approval in GitHub
```

Check **Actions** tab in GitHub to see the deployment pipeline running.

---

## 🔄 Phase 6: MLOps Lifecycle Demo

### Step 6.1: Review Feedback Data
```bash
# Check DynamoDB for user feedback
aws dynamodb scan --table-name llmops-feedback-log --region us-east-1
```

### Step 6.2: Update Knowledge Base
Add new Q&A to `data_pipeline/data/it_support_faq.csv`:
```csv
How do I reset my password?,"Go to portal.company.com/password-reset and enter your email. You'll receive a reset link within 5 minutes."
```

### Step 6.3: Trigger Automated Redeployment
```bash
# Update vector store
cd data_pipeline
python process_data.py  # This uploads new FAISS index to S3

# Commit and push to trigger CI/CD
git add data_pipeline/data/it_support_faq.csv
git commit -m "feat: Add password reset FAQ"
git push origin main

# GitHub Actions will:
# 1. Build new Docker image
# 2. Push to ECR
# 3. Update Kubernetes deployment
# 4. Rolling update with zero downtime
```

---

## ✅ Verification Checklist

- [ ] AWS infrastructure created (S3, ECR, DynamoDB, EKS)
- [ ] Data pipeline runs and uploads FAISS index to S3
- [ ] Docker image builds and pushes to ECR
- [ ] Kubernetes deployment successful with LoadBalancer
- [ ] API endpoints respond correctly
- [ ] Prometheus metrics collecting
- [ ] Grafana dashboard showing data
- [ ] GitHub Actions secrets configured
- [ ] CI/CD pipeline triggers on push
- [ ] MLOps cycle works (update data → auto-deploy)

## 🎯 Success Metrics

Your system is working when:
1. **Chat API** responds with relevant answers
2. **Feedback API** stores data in DynamoDB
3. **Metrics** show in Grafana (requests, latency, tokens)
4. **CI/CD** auto-deploys on code changes
5. **Zero downtime** during updates

## 🔧 Troubleshooting

**Pod not starting?**
```bash
kubectl describe pod -l app=llmops-chatbot
kubectl logs -l app=llmops-chatbot
```

**API not responding?**
```bash
kubectl get svc llmops-chatbot-service
kubectl port-forward svc/llmops-chatbot-service 8080:80
curl http://localhost:8080/health
```

**FAISS index not loading?**
- Verify S3 bucket permissions
- Check S3 objects exist: `aws s3 ls s3://llmops-knowledge-base/faiss_index/`

---

## 🎉 Next Steps

1. **Scale**: Increase EKS nodes for production load
2. **Security**: Use IAM roles instead of access keys
3. **Advanced Monitoring**: Add custom metrics and alerts
4. **A/B Testing**: Deploy multiple model versions
5. **Data Drift**: Monitor input distribution changes

Your production LLMOps pipeline is now complete! 🚀
