import httpx
import json
import asyncio
from time import sleep
from bs4 import BeautifulSoup
import os
from datetime import datetime

# ======= CONFIG =======
BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
CATEGORY_SLUG = "courses/tds-kb" 
CATEGORY_ID = 34  # Tools in Data Science
DATE_START = datetime(2025, 1, 1)
DATE_END = datetime(2025, 4, 14)
OUTPUT_FILE = "discourse_posts.json"

# ======= HELPERS =======
def load_cookie():
    with open("secrets.json", "r") as f:
        secrets = json.load(f)
    return secrets["cookie"]

def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def parse_date(datestr):
    try:
        return datetime.strptime(datestr, "%Y-%m-%dT%H:%M:%S.%fZ")
    except:
        return None

def save_to_file(data, filename=OUTPUT_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved {len(data)} topics to {filename}")

def load_existing_data(filename=OUTPUT_FILE):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ======= SCRAPER LOGIC =======
async def fetch_topic_list(client, category_id, max_pages=20):
    CATEGORY_SLUG = "courses/tds-kb"
    all_topics = []

    for page in range(0, max_pages):
        url = f"{BASE_URL}/c/{CATEGORY_SLUG}/{category_id}/l/latest.json?page={page}"
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 404:
            break  # No more pages
        resp.raise_for_status()
        data = resp.json()
        topics = data.get("topic_list", {}).get("topics", [])
        if not topics:
            break
        all_topics.extend([(topic["id"], topic["title"], topic["slug"]) for topic in topics])
        await asyncio.sleep(0.3)  # be polite

    return all_topics



async def fetch_topic_posts(client, topic_id):
    url = f"{BASE_URL}/t/{topic_id}.json"
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    posts = []
    for post in data["post_stream"]["posts"]:
        created_at = parse_date(post.get("created_at", ""))
        if created_at and DATE_START <= created_at <= DATE_END:
            text = html_to_text(post.get("cooked", ""))
            posts.append(text)
    return posts

async def scrape_all_topics(category_id, headers):
    all_data = load_existing_data()
    processed_ids = {entry["topic_id"] for entry in all_data}

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        topics = await fetch_topic_list(client, category_id)
        for topic_id, title, slug in topics:
            if topic_id in processed_ids:
                continue
            try:
                print(f"🔍 Fetching topic {topic_id} - {title} - {slug}")
                posts = await fetch_topic_posts(client, topic_id)
                if posts:
                    all_data.append({
                        "topic_id": topic_id,
                        "title": title,
                        "url": f"{BASE_URL}/t/{slug}/{topic_id}",
                        "posts": posts
                    })
                    save_to_file(all_data)
                await asyncio.sleep(0.5)  # Be nice
            except httpx.HTTPError as e:
                print(f"⚠️  Failed topic {topic_id}: {e}")
    return all_data


# ======= MAIN =======
if __name__ == "__main__":
    cookie = load_cookie()
    headers = {
        "cookie": cookie,
        "user-agent": "Mozilla/5.0"
    }
    asyncio.run(scrape_all_topics(CATEGORY_ID, headers))
