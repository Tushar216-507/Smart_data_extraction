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
from openai import OpenAI
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

client = OpenAI(
    api_key=Config.NVIDIA_API_KEY,
    base_url=Config.NVIDIA_BASE_URL
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


def verify_links(candidates):
    """Checks a list of CandidateURLs concurrently, returns only the working ones."""
    working = set()
    with ThreadPoolExecutor(max_workers=LINK_CHECK_WORKERS) as executor:
        futures = {executor.submit(check_link_alive, c.url): c.url for c in candidates}
        for i, future in enumerate(as_completed(futures), 1):
            url, alive = future.result()
            if alive:
                working.add(url)
            if i % 25 == 0:
                print(f"  checked {i}/{len(candidates)} links...")
    # Preserve the original ranking order
    return [c for c in candidates if c.url in working]

def fetch_page_metadata(candidate):
    """
    Downloads a page and extracts useful metadata into the CandidateURL.
    """
    try:
        response = requests.get(
            candidate.url,
            headers=HEADERS,
            timeout=LINK_CHECK_TIMEOUT
        )
        response.encoding = response.apparent_encoding
        if response.status_code >= 400:
            return None

        soup = BeautifulSoup(response.content, "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        
        h1_tag = soup.find("h1")
        h1 = h1_tag.get_text(" ", strip=True) if h1_tag else ""
        
        structured_data = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, list):
                    structured_data.extend(data)
                else:
                    structured_data.append(data)
            except Exception:
                pass

        candidate.metadata.update({
            "title": title,
            "h1": h1,
            "status": response.status_code,
            "structured_data": structured_data
        })

        return candidate
    except Exception:
        return None
    
def translate_batch(candidates):

    if not candidates:
        return candidates

    payload = []

    for i, candidate in enumerate(candidates):
        payload.append({
            "id": i,
            "title": candidate.metadata.get("title", ""),
            "h1": candidate.metadata.get("h1", "")
        })

    example = {
        "pages": [
            {
                "id": 0,
                "title_en": "",
                "h1_en": "",
                "page_type": "Degree Programme"
            }
        ]
    }

    prompt = f"""
    Translate all university programme metadata to English.
    AND classify the page_type as exactly one of: Degree Programme, Programme Hub, Degree Catalogue, Admissions, Support, Navigation, Other.

    Rules:
    - Return ONLY valid JSON.
    - Keep academic meaning.
    - Translate German university terminology naturally.
    - Classify accurately.
    - Do not invent information.
    - Preserve ids.

    Input:

    {json.dumps(payload, ensure_ascii=False, indent=2)}

    Return exactly this schema:

    {json.dumps(example, indent=2)}
"""

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=Config.NVIDIA_MODEL,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            break
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue
            raise

    translated = json.loads(
        response.choices[0].message.content
    )["pages"]

    lookup = {item["id"]: item for item in translated}

    for i, candidate in enumerate(candidates):

        if i not in lookup:
            continue

        item = lookup[i]

        candidate.metadata["title_original"] = candidate.metadata.get("title", "")
        candidate.metadata["h1_original"] = candidate.metadata.get("h1", "")
        candidate.metadata["title_en"] = item.get("title_en", "")
        candidate.metadata["h1_en"] = item.get("h1_en", "")
        candidate.page_type = item.get("page_type", "Unknown")

    return candidates

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

    candidates = discovery_result.candidates

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

    working_candidates = verify_links(candidates)

    print(f"  {len(working_candidates)}/{len(candidates)} links are working")

    print("\nStep 5: Extracting page metadata...")

    program_candidates = []

    print("\nFetching metadata...")

    METADATA_WORKERS = 25

    with ThreadPoolExecutor(max_workers=METADATA_WORKERS) as executor:

        futures = {
            executor.submit(fetch_page_metadata, candidate): candidate
            for candidate in working_candidates
        }

        for index, future in enumerate(as_completed(futures), start=1):

            updated_candidate = future.result()

            if updated_candidate:
                program_candidates.append(updated_candidate)

            if index % 25 == 0:
                print(f"  fetched {index}/{len(working_candidates)}")

    # Restore the original URL ranking because threads finish out of order.
    program_candidates.sort(key=lambda c: c.score, reverse=True)

    print("\nTranslating metadata & Classifying intents...")

    BATCH_SIZE = 20

    for start in range(0, len(program_candidates), BATCH_SIZE):

        batch = program_candidates[start:start+BATCH_SIZE]

        print(
            f"  processing batch "
            f"{start//BATCH_SIZE + 1}"
        )

        if ENABLE_TRANSLATION:
            translate_batch(batch)
        else:
            for c in batch:
                c.metadata["title_original"] = c.metadata.get("title", "")
                c.metadata["h1_original"] = c.metadata.get("h1", "")
                c.metadata["title_en"] = c.metadata.get("title", "")
                c.metadata["h1_en"] = c.metadata.get("h1", "")
                c.page_type = "Unknown"

    print("\nRe-evaluating candidates based on metadata...")
    from discovery.evaluation import CandidateEvaluator
    evaluator = CandidateEvaluator()
    for c in program_candidates:
        evaluator.evaluate(c)

    program_candidates.sort(key=lambda x: x.score, reverse=True)
    print()
    print("\nTop 10 Ranked Program Candidates")
    print("-" * 120)

    for i, c in enumerate(program_candidates[:10], start=1):
        print(
            f"{i:2d}. "
            f"Score={c.score:4} | "
            f"Type={c.page_type:18} | "
            f"Title={c.metadata.get('title_en', '')[:60]} | "
            f"H1={c.metadata.get('h1_en', '')[:60]}"
        )
        print(f"    URL: {c.url}")
        print(f"    Reasons: {c.reasons}")
        print()

    print(f"\nDiscovery complete. Found {len(program_candidates)} working program URLs.")
    
    program_pages = []
    for c in program_candidates:
        page_data = {
            "url": c.url,
            "status": c.metadata.get("status", 200),
            "title": c.metadata.get("title", ""),
            "h1": c.metadata.get("h1", ""),
            "title_original": c.metadata.get("title_original", ""),
            "h1_original": c.metadata.get("h1_original", ""),
            "title_en": c.metadata.get("title_en", ""),
            "h1_en": c.metadata.get("h1_en", ""),
            "page_type": c.page_type,
            "score": c.score,
            "reasons": c.reasons
        }
        program_pages.append(page_data)

    return {
        "university_base_url": base_url,
        "total_working_program_urls": len(program_pages),
        "program_urls": program_pages,
    }


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
