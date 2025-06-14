import json
from typing import List
from tqdm import tqdm
import tiktoken

# Load tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")

# Configurable chunking
MAX_TOKENS = 500
OVERLAP = 50

def chunk_text(text: str) -> List[str]:
    tokens = tokenizer.encode(text)
    chunks = []
    for start in range(0, len(tokens), MAX_TOKENS - OVERLAP):
        chunk = tokens[start: start + MAX_TOKENS]
        chunks.append(tokenizer.decode(chunk))
        if start + MAX_TOKENS >= len(tokens):
            break
    return chunks

def main():
    with open("discourse_posts.json", "r", encoding="utf-8") as f:
        discourse = json.load(f)

    with open("tds_course_content.json", "r", encoding="utf-8") as f:
        course = json.load(f)

    output = []

    for entry in tqdm(discourse, desc="Processing Discourse"):
        full_text = entry["title"] + "\n" + "\n".join(entry["posts"])
        chunks = chunk_text(full_text)
        for i, chunk in enumerate(chunks):
            output.append({
                "id": f"discourse-{entry['topic_id']}-{i}",
                "source": "discourse",
                "title": entry["title"],
                "url": entry["url"],  # Use the full URL from the JSON
                "content": chunk
            })

    for entry in tqdm(course, desc="Processing Course"):
        full_text = entry.get("content", "")
        chunks = chunk_text(full_text)
        for i, chunk in enumerate(chunks):
            output.append({
                "id": f"course-{entry['menu_text'].replace(' ', '_')}-{i}",
                "source": "course",
                "title": entry["menu_text"],
                "url": entry["url"],
                "content": chunk
            })

    with open("docs.jsonl", "w", encoding="utf-8") as f:
        for record in output:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✅ Saved {len(output)} chunks to docs.jsonl")

if __name__ == "__main__":
    main()
