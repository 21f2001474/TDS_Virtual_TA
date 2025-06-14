import json
import psycopg2
from openai import OpenAI
from tqdm import tqdm

# Load secrets
with open("secrets.json") as f:
    secrets = json.load(f)

client = OpenAI(
    api_key=secrets["aipipe_token"],
    base_url="https://aipipe.org/openai/v1"
)

conn = psycopg2.connect(secrets["pg_uri"])
cursor = conn.cursor()

with open("docs.jsonl", "r", encoding="utf-8") as f:
    for line in tqdm(f, desc="Inserting embeddings"):
        doc = json.loads(line)
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=doc["content"]
            )
            vector = response.data[0].embedding

            cursor.execute(
                """
                INSERT INTO documents (id, source, title, url, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (
                    doc["id"],
                    doc["source"],
                    doc["title"],
                    doc["url"],
                    doc["content"],
                    vector
                )
            )

        except Exception as e:
            print(f"❌ Failed on {doc['id']}: {e}")

conn.commit()
cursor.close()
conn.close()

print("✅ Embeddings inserted into PostgreSQL.")
