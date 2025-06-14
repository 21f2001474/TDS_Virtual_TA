import asyncio
import json
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://tds.s-anand.net/#/2025-01/"
OUTPUT_FILE = "tds_course_content.json"

def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)

async def scrape_course():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        page = await browser.new_page()
        try:
            print(f"🔗 Opening {BASE_URL}")
            await page.goto(BASE_URL, timeout=90000)
            print("⏳ Waiting for sidebar (aside)...")
            await page.wait_for_selector("aside", timeout=90000)
        except Exception as e:
            print(f"❌ Failed to load sidebar: {e}")
            html = await page.content()
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("⚠️ Dumped page HTML to debug_page.html")
            await browser.close()
            return

        # Expand all menus
        for summary in await page.query_selector_all("summary"):
            try:
                await summary.click()
            except:
                pass

        # Get all links from sidebar
        sidebar_links = await page.query_selector_all("aside a")
        links = []
        for link in sidebar_links:
            href = await link.get_attribute("href")
            text = await link.inner_text()
            if href and href.startswith("#/"):
                links.append((href, text))

        print(f"📚 Found {len(links)} sidebar links")

        course_data = []

        for href, link_text in links:
            full_url = "https://tds.s-anand.net/" + href
            print(f"🔍 Visiting: {link_text} - {full_url}")
            try:
                await page.goto(full_url, timeout=60000)
                await page.wait_for_selector("main", timeout=10000)
                html = await page.inner_html("main")
                text = html_to_text(html)
                title = await page.title()

                course_data.append({
                    "url": full_url,
                    "title": title,
                    "menu_text": link_text,
                    "content": text
                })
            except Exception as e:
                print(f"⚠️ Skipped {href}: {e}")

        await browser.close()

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(course_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved {len(course_data)} items to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(scrape_course())
