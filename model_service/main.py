import os
import uuid
import tempfile
import boto3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain.chains import RetrievalQA
from langchain_community.llms import HuggingFaceHub
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter
from transformers import AutoTokenizer


# Environment configuration
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_FAISS_PREFIX = os.getenv("S3_FAISS_PREFIX", "faiss_index")
HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
DYNAMODB_TABLE = os.getenv("DYNAMODB_FEEDBACK_TABLE")


app = FastAPI(title="LLMOps Chatbot")
qa_chain = None
tokenizer = None


# Prometheus Metrics
PROMPT_TOKENS_COUNTER = Counter("chatbot_prompt_tokens_total", "Total prompt tokens")
COMPLETION_TOKENS_COUNTER = Counter("chatbot_completion_tokens_total", "Total completion tokens")


def download_faiss_from_s3(local_dir: str) -> None:
    """Download FAISS index folder from S3 into local_dir."""
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    prefix = f"{S3_FAISS_PREFIX}/"
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            rel = key[len(prefix) :]
            dest_path = os.path.join(local_dir, rel)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            s3.download_file(S3_BUCKET, key, dest_path)


@app.on_event("startup")
def startup_event() -> None:
    global qa_chain, tokenizer

    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET_NAME env var is required")
    # HF_TOKEN not required for open models like flan-t5-small

    # Initialize tokenizer with open model (no authentication needed)
    tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")

    # Initialize components
    embed_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Download and load vector store from S3
    local_index_dir = os.path.join(tempfile.gettempdir(), "faiss_index")
    os.makedirs(local_index_dir, exist_ok=True)
    download_faiss_from_s3(local_index_dir)
    vectorstore = FAISS.load_local(local_index_dir, embed_model, allow_dangerous_deserialization=True)

    # Initialize LLM with open model (no token needed)
    llm = HuggingFaceHub(
        repo_id="google/flan-t5-small",
        model_kwargs={"temperature": 0.1, "max_length": 512},
    )

    qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vectorstore.as_retriever())


# Enable Prometheus metrics
Instrumentator().instrument(app).expose(app)


# API Models
class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    answer: str
    query_id: str


class FeedbackRequest(BaseModel):
    query_id: str
    query: str
    answer: str
    is_correct: bool


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not qa_chain or not tokenizer:
        raise HTTPException(status_code=503, detail="Service initializing")

    # Token counting
    prompt_tokens = len(tokenizer.encode(req.query))
    PROMPT_TOKENS_COUNTER.inc(prompt_tokens)

    result = qa_chain.run(req.query)

    completion_tokens = len(tokenizer.encode(result))
    COMPLETION_TOKENS_COUNTER.inc(completion_tokens)

    return {"answer": result, "query_id": str(uuid.uuid4())}


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    if not DYNAMODB_TABLE:
        raise HTTPException(status_code=500, detail="DynamoDB table not configured")
    table = boto3.resource("dynamodb").Table(DYNAMODB_TABLE)
    table.put_item(Item=req.dict())
    return {"status": "Feedback recorded"}


