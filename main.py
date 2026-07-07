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
import re
import json
import requests
from groq import Groq
import os
import json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

import sitemap
import crawler
from config import Config

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
DEGREE_KEYWORDS_SAFE = [
    "bachelor", "bachelors", "undergraduate",
    "master", "masters", "postgraduate",
    # German equivalents (common for DE/AT/CH universities)
    "bachelorstudium", "masterstudium",
]

DEGREE_KEYWORDS_BOUNDARY = [
    r"b\.sc", r"bsc", r"b\.a\b",
    r"m\.sc", r"msc", r"m\.a\b",
]
DEGREE_BOUNDARY_PATTERN = re.compile(
    r"(?<![a-z])(" + "|".join(DEGREE_KEYWORDS_BOUNDARY) + r")(?![a-z])"
)

# Anything containing these is almost certainly NOT a program page, regardless of
# whether it also matches a degree keyword above (e.g. "postdoc career programme",
# "alumni mentoring program", a news article mentioning "master's degree").
EXCLUDE_KEYWORDS = [
    "news", "newsroom", "press", "pressemitteilung", "media-relations",
    "event", "veranstaltung", "calendar",
    "alumni", "career", "cooperation", "mentoring",
    "contact", "kontakt", "faq",
    "examination-office", "pruefungsamt",
    "admission", "application", "deadline",
    "job", "stelle", "vacancy",
    "workspace-for-students",
    "prize", "award", "thesis", "auszeichnung",
]

# Detail-page pattern seen on many university catalogs: a subject slug followed
# by a trailing numeric ID, e.g. .../data-science-master-4464.html
# This is a strong (but optional) signal - real catalog entries are usually
# generated from a database and follow this template; blog/news pages don't.
DETAIL_PAGE_PATTERN = re.compile(r"-\d+\.html$")

client = Groq(
    api_key=Config.GROQ_API_KEY
)


def looks_like_program_url(url):
    """
    A URL qualifies if:
      - it contains a degree-level keyword (bachelor/master/etc), AND
      - it does NOT contain an exclude keyword (news, alumni, career, etc)
    The numeric-ID detail-page pattern is treated as a bonus signal, not a hard
    requirement, since not every university's catalog uses that convention.
    """
    lower = url.lower()

    if any(bad in lower for bad in EXCLUDE_KEYWORDS):
        return False

    if any(keyword in lower for keyword in DEGREE_KEYWORDS_SAFE):
        return True

    return bool(DEGREE_BOUNDARY_PATTERN.search(lower))


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

def run(base_url):
    print(f"\nStarting discovery for: {base_url}\n")

    # --- Step 1: Sitemap ---
    print("Step 1: Fetching sitemap URLs...")
    sitemap_urls = sitemap.get_all_sitemap_urls(base_url)
    print(f"  Found {len(sitemap_urls)} total URLs in sitemap(s)")

    all_urls = set(sitemap_urls)

    # --- Step 2: Fallback crawl if sitemap was thin or missing ---
    if len(sitemap_urls) < MIN_SITEMAP_URLS_BEFORE_FALLBACK:
        print(f"\nStep 2: Sitemap gave < {MIN_SITEMAP_URLS_BEFORE_FALLBACK} URLs, falling back to crawler...")
        crawled_urls = crawler.crawl(base_url, max_pages=MAX_CRAWL_PAGES)
        print(f"  Crawler found {len(crawled_urls)} URLs")
        all_urls.update(crawled_urls)
    else:
        print("\nStep 2: Sitemap gave enough URLs, skipping fallback crawl")

    print(f"\nTotal unique URLs collected: {len(all_urls)}")

    # --- Step 3: Filter for program/course-looking URLs ---
    print("\nStep 3: Filtering for program/course URLs...")
    candidates = [u for u in all_urls if looks_like_program_url(u)]
    print(f"  {len(candidates)} candidate program URLs after keyword filter")

    if not candidates:
        print("\nNo candidate URLs found. Try lowering MIN_SITEMAP_URLS_BEFORE_FALLBACK "
              "or check if the site blocks bots.")
        return

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

    # --- Step 5: Save output ---
    result = {
        "university_base_url": base_url,
        "total_working_program_urls": len(program_pages),
        "program_urls": program_pages,
    }

    with open("output1.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Saved {len(working_urls)} working program URLs to output.json\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <university_base_url>")
        print("Example: python main.py https://www.lmu.de")
        sys.exit(1)

    target_url = sys.argv[1].rstrip("/")
    run(target_url)