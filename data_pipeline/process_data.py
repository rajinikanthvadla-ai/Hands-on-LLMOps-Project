import os
import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
import boto3

# Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "llmops-knowledge-base")  # default bucket name
S3_FAISS_PREFIX = os.getenv("S3_FAISS_PREFIX", "faiss_index")
LOCAL_FAISS_PATH = "faiss_index_local"


def main() -> None:
    print("🔧 Initializing embedding model...")
    embed_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print("📚 Loading data...")
    df = pd.read_csv("data/it_support_faq.csv")
    texts = (df["question"] + " \nAnswer: " + df["answer"]).tolist()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.create_documents(texts)

    print("🔄 Creating FAISS vector index...")
    vectorstore = FAISS.from_documents(docs, embed_model)
    os.makedirs(LOCAL_FAISS_PATH, exist_ok=True)
    vectorstore.save_local(LOCAL_FAISS_PATH)

    print(f"☁️ Uploading index to S3 bucket '{S3_BUCKET_NAME}' under prefix '{S3_FAISS_PREFIX}'...")
    s3_client = boto3.client("s3")
    for file_name in os.listdir(LOCAL_FAISS_PATH):
        local_path = os.path.join(LOCAL_FAISS_PATH, file_name)
        s3_key = f"{S3_FAISS_PREFIX}/{file_name}"
        s3_client.upload_file(local_path, S3_BUCKET_NAME, s3_key)
        print(f"Uploaded {local_path} -> s3://{S3_BUCKET_NAME}/{s3_key}")

    print("✅ Data pipeline complete!")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
import os
import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
import boto3

# Configuration - UPDATE THIS WITH YOUR BUCKET NAME
S3_BUCKET_NAME = "llmops-knowledge-base"
S3_FAISS_INDEX_KEY = "faiss_index"
LOCAL_FAISS_PATH = "faiss_index_local"

def main():
    print("Initializing embedding model...")
    embed_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print("Loading data...")
    df = pd.read_csv("data/it_support_faq.csv")
    texts = (df['question'] + " \nAnswer: " + df['answer']).tolist()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.create_documents(texts)
    
    print("Creating FAISS vector index...")
    vectorstore = FAISS.from_documents(docs, embed_model)
    vectorstore.save_local(LOCAL_FAISS_PATH)
    
    print(f"Uploading index to S3 bucket: {S3_BUCKET_NAME}...")
    s3_client = boto3.client('s3')
    for file in os.listdir(LOCAL_FAISS_PATH):
        local_path = os.path.join(LOCAL_FAISS_PATH, file)
        s3_key = os.path.join(S3_FAISS_INDEX_KEY, file)
        s3_client.upload_file(local_path, S3_BUCKET_NAME, s3_key)
        print(f"Uploaded {file}")
    
    print("Data pipeline complete!")

if __name__ == "__main__":
    main()