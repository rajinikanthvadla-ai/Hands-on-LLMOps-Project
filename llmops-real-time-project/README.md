# LLMOps Real-Time Chatbot

Production-ready LLM chatbot with AWS, EKS, FastAPI, LangChain, Prometheus, and GitHub Actions.

## 🚀 Quick Start

See **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** for complete step-by-step setup.

### Local Pipeline (Windows PowerShell)

```powershell
# Set environment for data pipeline
$env:S3_BUCKET_NAME = "llmops-knowledge-base"
$env:S3_FAISS_PREFIX = "faiss_index"

# Build FAISS index and upload to S3
cd data_pipeline
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r ..\model_service\requirements.txt
pip install -U langchain-community langchain-text-splitters pandas boto3 faiss-cpu
python process_data.py
Deactivate
cd ..
```

## 📖 Full Documentation

- **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** - Complete setup guide
- **Architecture**: AWS EKS + FastAPI + LangChain + Prometheus
- **CI/CD**: GitHub Actions → ECR → Kubernetes rolling updates
- **Monitoring**: Grafana dashboards with LLM-specific metrics


