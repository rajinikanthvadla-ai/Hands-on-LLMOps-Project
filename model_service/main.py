import os
import uuid
import tempfile
import boto3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain.chains import RetrievalQA
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.llms.base import LLM
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter
from transformers import AutoTokenizer, pipeline
from typing import Optional, List, Any


# Environment configuration
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_FAISS_PREFIX = os.getenv("S3_FAISS_PREFIX", "faiss_index")
DYNAMODB_TABLE = os.getenv("DYNAMODB_FEEDBACK_TABLE")


# Simple local LLM that doesn't need HuggingFace Hub authentication
class LocalLLM:
    def __init__(self):
        # Use a small, fast model that doesn't need authentication
        self.text_generator = pipeline("text-generation", model="distilgpt2", device=-1)
    
    def __call__(self, prompt: str) -> str:
        # Generate response using local model
        try:
            response = self.text_generator(prompt, max_length=150, num_return_sequences=1, 
                                         pad_token_id=50256, do_sample=True, temperature=0.7)
            generated_text = response[0]['generated_text']
            
            # Clean up the response (remove the original prompt)
            if generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt):].strip()
            
            # Return a meaningful response or default
            return generated_text[:200] if generated_text else "I understand your question. Let me help you with that."
        except Exception as e:
            return f"I can help you with your question. Please provide more details."


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

    # Initialize tokenizer with simple model (no authentication needed)
    tokenizer = AutoTokenizer.from_pretrained("distilgpt2")

    # Initialize components
    embed_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Download and load vector store from S3
    local_index_dir = os.path.join(tempfile.gettempdir(), "faiss_index")
    os.makedirs(local_index_dir, exist_ok=True)
    download_faiss_from_s3(local_index_dir)
    vectorstore = FAISS.load_local(local_index_dir, embed_model, allow_dangerous_deserialization=True)

    # Initialize local LLM (no HuggingFace Hub needed)
    local_llm = LocalLLM()
    
    # Simple QA function that combines retrieval with local generation
    def simple_qa(question: str) -> str:
        # Get relevant documents from vector store
        docs = vectorstore.similarity_search(question, k=3)
        
        # Combine context from retrieved documents
        context = "\n".join([doc.page_content for doc in docs])
        
        # Create a prompt with context
        prompt = f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"
        
        # Generate response using local model
        response = local_llm(prompt)
        return response if response else "I can help you with IT support questions based on our knowledge base."
    
    # Store the QA function globally
    qa_chain = simple_qa


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

    # Call the QA function directly
    result = qa_chain(req.query)

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


