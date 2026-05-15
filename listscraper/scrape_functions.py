# Core scraping functions go here

import time
import threading
import requests
import concurrent.futures
from bs4 import BeautifulSoup
from pprint import pprint
from tqdm import tqdm

from listscraper.utility_functions import build_film_url, build_histogram_url, parse_rating_histogram

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

_request_lock = threading.Lock()
_last_request_time = 0.0

def _get(url: str) -> BeautifulSoup | None:
    """
    Shared GET helper. Returns a BeautifulSoup object or None on failure.
    Uses a threading lock to ensure at least 0.1s between requests globally.
    """
    global _last_request_time
    with _request_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < 0.1:
            time.sleep(0.1 - elapsed)
        _last_request_time = time.time()
        
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"Warning: {url} returned {response.status_code}")
            return None
        return BeautifulSoup(response.text, "lxml")
    except requests.RequestException as e:
        print(f"Warning: request to {url} failed — {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 1. get_film_urls
# ──────────────────────────────────────────────────────────────────────────────

def get_film_urls(list_url: str, page_number: int) -> tuple[list[str], bool]:
    """
    Return (film_urls, has_next_page) for one page of a Letterboxd list/watchlist.

    Args:
        list_url:    Base URL of the list (no trailing /page/N/).
        page_number: 1-indexed page number to fetch.

    Returns:
        film_urls    — list of full https://letterboxd.com/film/{slug}/ URLs.
        has_next_page — True if a paginated next page exists.
    """
    # Build paginated URL
    base = list_url.rstrip("/")
    paginated_url = f"{base}/page/{page_number}/"

    soup = _get(paginated_url)
    if soup is None:
        return [], False

    film_urls: list[str] = []

    # Films live in <div> elements with data-target-link or data-film-slug inside <ul class="poster-list">
    # Let's use select for flexibility:
    for div in soup.select("li .react-component, li div[data-target-link], li div[data-film-slug]"):
        slug = ""
        if div.get("data-item-slug"):
            slug = div["data-item-slug"]
        elif div.get("data-target-link"):
            slug = div["data-target-link"].strip("/").split("/")[-1]
        elif div.get("data-film-slug"):
            slug = div["data-film-slug"]
            
        if slug:
            film_urls.append(build_film_url(slug))

    if not film_urls:
        # Fallback: search whole page
        for div in soup.select("div[data-target-link], div[data-film-slug], div[data-item-slug]"):
            slug = ""
            if div.get("data-item-slug"):
                slug = div["data-item-slug"]
            elif div.get("data-target-link"):
                slug = div["data-target-link"].strip("/").split("/")[-1]
            elif div.get("data-film-slug"):
                slug = div["data-film-slug"]
            
            if slug:
                film_urls.append(build_film_url(slug))


    # Detect next page
    has_next_page = soup.find("a", class_="next") is not None

    return film_urls, has_next_page


# ──────────────────────────────────────────────────────────────────────────────
# 2. scrape_film
# ──────────────────────────────────────────────────────────────────────────────

def scrape_film(film_url: str) -> dict | None:
    """
    Scrape a single Letterboxd film page and return a data dictionary.

    Keys: title, year, director, cast, average_rating, rating_count,
          rating_histogram, fan_count, letterboxd_url.

    Returns None if the page request fails entirely.
    """
    try:
        soup = _get(film_url)
        if soup is None:
            return None

        data: dict = {"letterboxd_url": film_url}

        # ── Title ──────────────────────────────────────────────────────────
        title_tag = soup.find("h1", class_="filmtitle")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)
        else:
            og_title = soup.find("meta", property="og:title")
            data["title"] = og_title["content"].strip() if og_title else None

        # ── Year ───────────────────────────────────────────────────────────
        import re
        year = None
        # 1) <a href="/films/year/YYYY/"> link on the page
        year_a = soup.find("a", href=re.compile(r"/films/year/\d{4}/"))
        if year_a:
            m = re.search(r"(\d{4})", year_a["href"])
            year = m.group(1) if m else year_a.get_text(strip=True)
        if not year:
            # 2) og:title — "Film Title (YYYY)"
            og_title = soup.find("meta", property="og:title")
            if og_title:
                m = re.search(r"\((\d{4})\)", og_title.get("content", ""))
                year = m.group(1) if m else None
        data["year"] = year

        # ── Director ───────────────────────────────────────────────────────
        data["director"] = _extract_director(soup)

        # ── Cast (top 5) ───────────────────────────────────────────────────
        data["cast"] = _extract_cast(soup)

        # ── Average rating — twitter:data2 meta tag on the main page ───────
        avg_rating = None
        tw_rating = soup.find("meta", attrs={"name": "twitter:data2"})
        if tw_rating:
            m = re.search(r"([\d.]+)\s+out of", tw_rating.get("content", ""))
            avg_rating = float(m.group(1)) if m else None
        data["average_rating"] = avg_rating

        # ── rating_count — embedded in inline script JSON ──────────────────
        # Letterboxd injects {"ratingCount": N, ...} into a <script> block.
        rating_count = None
        for script in soup.find_all("script"):
            txt = script.string or ""
            if "ratingCount" in txt:
                m = re.search(r'"ratingCount"\s*:\s*(\d+)', txt)
                if m:
                    rating_count = int(m.group(1))
                break
        data["rating_count"] = rating_count

        # ── Rating histogram (ESI endpoint — optional, 403 on some regions) ─
        histogram_url = build_histogram_url(film_url)
        hist_soup = _get(histogram_url)

        rating_histogram = None
        fan_count = None

        if hist_soup:
            rating_histogram = parse_rating_histogram(str(hist_soup))

            # fan count — look for the "X fans" text in the histogram fragment
            fans_tag = hist_soup.find(class_=lambda c: c and "fan" in c.lower())
            if fans_tag:
                m = re.search(r"([\d,]+)", fans_tag.get_text())
                if m:
                    raw = int(m.group(1).replace(",", ""))
                    fan_count = round(raw / 100) * 100

        data["rating_histogram"] = rating_histogram
        data["fan_count"] = fan_count

        return data

    except Exception as e:
        print(f"Warning: failed to scrape {film_url} — {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_director(soup: BeautifulSoup) -> str | None:
    """Extract director name(s) from the film page."""
    # Primary: crew tab
    crew_div = soup.find("div", id="tab-crew")
    if crew_div:
        for block in crew_div.find_all("div", class_=lambda c: c and "crew-list" in c):
            label = block.find(class_=lambda c: c and "label" in c.lower())
            if label and "director" in label.get_text(strip=True).lower():
                names = [a.get_text(strip=True) for a in block.find_all("a")]
                return ", ".join(names) if names else None

        # Fallback within crew tab — first <a> after a "Director" heading
        for h3 in crew_div.find_all(["h3", "dt", "label"]):
            if "director" in h3.get_text(strip=True).lower():
                sibling = h3.find_next("a")
                if sibling:
                    return sibling.get_text(strip=True)

    # Last resort: meta description often has "Directed by X"
    import re
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        m = re.search(r"[Dd]irected by ([^.]+)", meta_desc.get("content", ""))
        if m:
            return m.group(1).strip()

    return None


def _extract_cast(soup: BeautifulSoup, top_n: int = 5) -> list[str]:
    """Extract top N cast members from the film page."""
    cast_div = soup.find("div", id="tab-cast")
    if cast_div:
        names = [a.get_text(strip=True) for a in cast_div.find_all("a")]
        return names[:top_n]
    return []
# ──────────────────────────────────────────────────────────────────────────────
# 3. get_all_film_urls
# ──────────────────────────────────────────────────────────────────────────────

def get_all_film_urls(base_url: str, page_range: tuple[int, int] | None = None) -> list[str]:
    """
    Takes a cleaned, validated Letterboxd list URL and an optional page_range (start, end).
    Fetches all film URLs across pages.
    """
    from listscraper.checkimport_functions import detect_url_type
    
    url_type = detect_url_type(base_url)
    print(f"Detected URL type: {url_type}")
    
    if url_type == "unknown":
        print("Warning: URL type is 'unknown'. Attempting to scrape as a list fallback.")
        
    start_page = 1
    end_page = float('inf')
    if page_range:
        start_page, end_page = page_range
        
    all_urls = []
    current_page = start_page
    
    while current_page <= end_page:
        urls, has_next = get_film_urls(base_url, current_page)
        
        if not urls and current_page > 1:
            # Assume pagination has ended and stop gracefully
            break
            
        print(f"Page {current_page}: found {len(urls)} films")
        all_urls.extend(urls)
        
        if not has_next:
            break
            
        current_page += 1
        
    # Deduplicate while preserving order
    deduplicated_urls = list(dict.fromkeys(all_urls))
    return deduplicated_urls


def scrape_all_films(film_urls: list[str], thread_count: int) -> list[dict]:
    """
    Takes a list of film URLs and a max thread count.
    Scrapes all URLs concurrently and returns a list of film dictionaries in the same order.
    """
    results_dict = {}
    failed_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
        # Submit all tasks and map futures to their original index
        future_to_index = {
            executor.submit(scrape_film, url): i 
            for i, url in enumerate(film_urls)
        }
        
        with tqdm(total=len(film_urls), desc="Scraping films", unit="film") as pbar:
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    if result is None:
                        failed_count += 1
                    else:
                        results_dict[index] = result
                except Exception as e:
                    print(f"Exception during scrape: {e}")
                    failed_count += 1
                finally:
                    pbar.update(1)
                    
    if failed_count > 0:
        print(f"{failed_count} films could not be scraped and were skipped")
        
    # Reconstruct list in original order, omitting Nones
    ordered_results = [results_dict[i] for i in range(len(film_urls)) if i in results_dict]
    return ordered_results


# ──────────────────────────────────────────────────────────────────────────────
# Quick test
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    TEST_URL = "https://letterboxd.com/film/parasite-2019/"
    print(f"Scraping: {TEST_URL}\n")
    result = scrape_film(TEST_URL)
    if result:
        pprint(result)
    else:
        print("Scrape returned None — check warnings above.")
