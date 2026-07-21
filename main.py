"""
main.py
-------
Entry point. Given a university's base URL, this:

  1. Pulls every URL from sitemap.xml (sitemap.py) - fast, usually gets 80%+
  2. If sitemap gives too few URLs, falls back to a BFS crawl (crawler.py)
  3. Filters the combined URL list for anything that looks like a
     program/course/degree page (bachelors + masters), staying generous
     to maximize recall
  4. Verifies each candidate URL is actually reachable (working link),
     dropping dead ones (404, timeout, connection error)
  5. Saves the final list of working program URLs to output.json

Usage:
    python main.py https://www.example-university.de
"""

import sys
import json
import requests
from groq import Groq
import json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config
from discovery.engine import DiscoveryEngine

# ---- Settings ----
MIN_SITEMAP_URLS_BEFORE_FALLBACK = 20   # if sitemap gives fewer than this, also crawl
MAX_CRAWL_PAGES = 500
LINK_CHECK_WORKERS = 20
LINK_CHECK_TIMEOUT = 8
ENABLE_TRANSLATION = True

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ProgramURLBot/1.0)"
}

# Strict degree-level keywords - a URL must contain one of these to be considered.
# NOTE: we deliberately dropped loose generic words like "program", "study", "course",
# "degree" - those matched far too much noise (press releases, alumni programs, research
# cooperation "programs", event calendars, etc). Requiring an actual degree-level term
# is what gets precision under control.
# Full words are checked with plain substring matching (safe - "bachelor" can't
# accidentally appear inside an unrelated word). Short fragments like "ba"/"ma"
# are checked with a word-boundary regex instead, since as plain substrings they
# false-matched inside ordinary words (e.g. "thema-finden" contains "ma-").

client = Groq(
    api_key=Config.GROQ_API_KEY
)

def check_link_alive(url):
    """Returns (url, is_alive). Tries HEAD first (cheap), falls back to GET."""
    try:
        resp = requests.head(url, headers=HEADERS, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True)
        if resp.status_code < 400:
            return url, True
        # Some servers don't support HEAD properly - retry with GET
        if resp.status_code in (403, 405):
            resp = requests.get(url, headers=HEADERS, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True)
            return url, resp.status_code < 400
        return url, False
    except requests.RequestException:
        return url, False


def verify_links(urls):
    """Checks a list of URLs concurrently, returns only the working ones."""
    working = []
    with ThreadPoolExecutor(max_workers=LINK_CHECK_WORKERS) as executor:
        futures = {executor.submit(check_link_alive, url): url for url in urls}
        for i, future in enumerate(as_completed(futures), 1):
            url, alive = future.result()
            if alive:
                working.append(url)
            if i % 25 == 0:
                print(f"  checked {i}/{len(urls)} links...")
    return sorted(working)

def fetch_page_metadata(url):
    """
    Downloads a page and extracts useful metadata.
    """

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=LINK_CHECK_TIMEOUT
        )

        response.encoding = response.apparent_encoding

        if response.status_code >= 400:
            return None

        soup = BeautifulSoup(response.content, "lxml")

        title = ""
        if soup.title:
            title = soup.title.get_text(" ", strip=True)

        h1 = ""
        h1_tag = soup.find("h1")
        if h1_tag:
            h1 = h1_tag.get_text(" ", strip=True)

        return {
            "url": url,
            "title": title,
            "h1": h1,
            'status': response.status_code
        }

    except Exception:
        return None
    
def translate_batch(pages):

    if not pages:
        return pages

    payload = []

    for i, page in enumerate(pages):
        payload.append({
            "id": i,
            "title": page["title"],
            "h1": page["h1"]
        })

    example = {
        "pages": [
            {
                "id": 0,
                "title_en": "",
                "h1_en": ""
            }
        ]
    }

    prompt = f"""
    Translate all university programme metadata to English.

    Rules:
    - Return ONLY valid JSON.
    - Keep academic meaning.
    - Translate German university terminology naturally.
    - Do not invent information.
    - Preserve ids.

    Input:

    {json.dumps(payload, ensure_ascii=False, indent=2)}

    Return exactly this schema:

    {json.dumps(example, indent=2)}
"""

    response = client.chat.completions.create(
        model=Config.GROQ_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    translated = json.loads(
        response.choices[0].message.content
    )["pages"]

    lookup = {item["id"]: item for item in translated}

    for i, page in enumerate(pages):

        if i not in lookup:
            continue

        item = lookup[i]

        page["title_original"] = page["title"]
        page["h1_original"] = page["h1"]

        page["title_en"] = item["title_en"]
        page["h1_en"] = item["h1_en"]

    return pages

def discover_programs(base_url):
    """
    Discover all programme URLs from a university website.

    This runs the complete discovery pipeline:
      1. Sitemap extraction
      2. Fallback BFS crawl (if sitemap is thin)
      3. Keyword filtering for programme URLs
      4. Link verification
      5. Page metadata extraction
      6. Metadata translation

    Returns:
        dict with keys:
            university_base_url  (str)
            total_working_program_urls  (int)
            program_urls  (list of programme metadata dicts)
    """
    print(f"\nStarting discovery for: {base_url}\n")

    # --- Step 1: Sitemap ---
    print("Step 1: Discovering programme URLs...")

    engine = DiscoveryEngine()

    discovery_result = engine.discover(base_url)

    candidates = [
        candidate.url
        for candidate in discovery_result.candidates
    ]

    print(f"  Found {len(candidates)} candidate URLs")

    if not candidates:
        print("\nNo candidate URLs found. Try lowering MIN_SITEMAP_URLS_BEFORE_FALLBACK "
              "or check if the site blocks bots.")
        return {
            "university_base_url": base_url,
            "total_working_program_urls": 0,
            "program_urls": [],
        }

    # --- Step 4: Verify links are actually working ---
    print(f"\nStep 4: Verifying {len(candidates)} links...")

    working_urls = verify_links(candidates)

    print(f"  {len(working_urls)}/{len(candidates)} links are working")

    print("\nStep 5: Extracting page metadata...")

    program_pages = []

    print("\nFetching metadata...")

    for index, url in enumerate(working_urls, start=1):

        page = fetch_page_metadata(url)

        if page:
            program_pages.append(page)

        if index % 25 == 0:
            print(f"  fetched {index}/{len(working_urls)}")

    print("\nTranslating metadata...")

    BATCH_SIZE = 20

    translated_pages = []

    for start in range(0, len(program_pages), BATCH_SIZE):

        batch = program_pages[start:start+BATCH_SIZE]

        print(
            f"  translating batch "
            f"{start//BATCH_SIZE + 1}"
        )

        if ENABLE_TRANSLATION:
            translated = translate_batch(batch)
            translated_pages.extend(translated)
        else:
            translated_pages.extend(batch)

    program_pages = translated_pages

    result = {
        "university_base_url": base_url,
        "total_working_program_urls": len(program_pages),
        "program_urls": program_pages,
    }

    print(f"\nDiscovery complete. Found {len(program_pages)} working program URLs.\n")

    return result


def save_discovery(result, output_file="output1.json"):
    """Save discovery result to a JSON file."""

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved {result['total_working_program_urls']} programs to {output_file}")


def run(base_url):
    """
    Run discovery and save to file.

    Kept for backward compatibility with standalone usage.
    """
    result = discover_programs(base_url)
    save_discovery(result)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <university_base_url>")
        print("Example: python main.py https://www.lmu.de")
        sys.exit(1)

    target_url = sys.argv[1].rstrip("/")
    run(target_url)
