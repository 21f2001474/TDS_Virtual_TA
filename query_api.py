from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
import psycopg2
import numpy as np
import json
from openai import OpenAI
import base64
import httpx
import mimetypes
from fastapi.middleware.cors import CORSMiddleware

# --- FastAPI app ---
app = FastAPI()

# --- Enable CORS (after app is created) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Load secrets ---
with open("secrets.json") as f:
    secrets = json.load(f)

# --- OpenAI via AI Pipe ---
client = OpenAI(
    api_key=secrets["aipipe_token"],
    base_url="https://aipipe.org/openai/v1"
)

# --- DB Connection ---
conn = psycopg2.connect(secrets["pg_uri"])
cursor = conn.cursor()


class QueryRequest(BaseModel):
    question: str
    image: Optional[str] = None  # base64-encoded string (data URL format)
    
def url_to_data_url(url: str) -> str:
    """Fetch image from URL and return base64 data URL"""
    resp = httpx.get(url)
    resp.raise_for_status()
    mime_type = mimetypes.guess_type(url)[0] or "image/png"
    encoded = base64.b64encode(resp.content).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

@app.post("/api/")
def semantic_answer(request: QueryRequest):
    # Step 1: Embed the question
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=request.question
    )
    vec = resp.data[0].embedding

    # Step 2: Semantic search in pgvector
    cursor.execute(
        """
        SELECT id, title, url, content
        FROM documents
        ORDER BY embedding <-> %s::vector
        LIMIT 5
        """,
        (vec,)
    )
    rows = cursor.fetchall()

    # Step 3: Build context
    context = "\n\n".join(row[3] for row in rows)

    # Step 4: Build GPT-4o message payload
    if request.image:
        image_url = request.image
        if image_url.startswith("http://") or image_url.startswith("https://"):
            image_url = url_to_data_url(image_url)  # convert to base64 data URL

        messages = [{
            "role": "user",
            "content": [
                {
                        "type": "text",
                        "text": f"""You are a TDS Virtual Teaching Assistant. Use only the context below to answer the question.

                        Context:
                        {context}

                        Question:
                        {request.question}"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }]
    else:
        messages = [{
            "role": "user",
            "content": f"""You are a TDS Virtual Teaching Assistant. Use only the context below to answer the question.

    Context:
    {context}

    Question:
    {request.question}"""
        }]
        
        # Step 5: Get GPT answer
        chat = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        answer = chat.choices[0].message.content

        # Step 6: Format links
        links = [{"url": row[2].replace("#/../", "#/"), "text": row[1]} for row in rows]

        return {"answer": answer, "links": links}
