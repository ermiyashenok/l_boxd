# Input validation and import functions go here

import os
from urllib.parse import urlparse

LETTERBOXD_HOST = "letterboxd.com"

def validate_and_clean_url(url: str) -> str:
    """Strips whitespace, ensures https://, and ensures trailing slash."""
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[7:]
    elif not url.startswith("https://"):
        url = "https://" + url
    
    if not url.endswith("/"):
        url += "/"
    return url

def detect_url_type(url: str) -> str:
    """Detect the type of Letterboxd URL based on its structure."""
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Could not parse the URL.")

    host = parsed.netloc.lower().lstrip("www.")
    if host != LETTERBOXD_HOST:
        raise ValueError(f"URL does not point to {LETTERBOXD_HOST} (got '{parsed.netloc}').")

    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return "unknown"

    if "list" in parts:
        return "list"
    
    if parts[-1] == "watchlist" or "watchlist" in parts:
        return "watchlist"

    cast_crew_keywords = {
        "actor", "director", "producer", "writer", "editor", "cinematography",
        "composer", "costumes", "make-up", "production-design", "art-direction",
        "visual-effects", "special-effects", "studio"
    }
    
    if len(parts) >= 2 and parts[1] == "films" and parts[0] not in cast_crew_keywords and parts[0] != "films":
        return "user_films"
        
    if parts[0] in cast_crew_keywords:
        return "cast_crew"
        
    if parts[0] == "films":
        return "generic"
        
    return "unknown"

def import_urls_from_file(filepath: str) -> list[str]:
    """Read a text file of URLs and return a list of cleaned URLs."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
        
    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(validate_and_clean_url(line))
    return urls

def validate_output_format(fmt: str) -> tuple[bool, str]:
    """Validate the requested output format string."""
    fmt = fmt.strip().lower()
    if fmt in ("csv", "json"):
        return True, fmt
    return False, f"Unsupported output format '{fmt}'. Choose 'csv' or 'json'."

def validate_page_limit(value: str) -> tuple[bool, int | str]:
    """Validate the --pages argument is a positive integer."""
    try:
        n = int(value)
        if n < 1:
            raise ValueError
        return True, n
    except (ValueError, TypeError):
        return False, f"Page limit must be a positive integer, got '{value}'."

if __name__ == "__main__":
    from listscraper.scrape_functions import get_all_film_urls

    test_urls = [
        " letterboxd.com/dave/list/official-top-250-narrative-feature-films ",
        "http://letterboxd.com/dave/watchlist",
        "https://letterboxd.com/dave/films/decade/1950s/genre/drama",
        "letterboxd.com/actor/song-kang-ho/",
        "https://letterboxd.com/films/popular/this/week/genre/documentary"
    ]
    
    print("--- URL Cleaning ---")
    for u in test_urls:
        print(f"Original: '{u}' -> Cleaned: '{validate_and_clean_url(u)}'")
        
    print("\n--- URL Type Detection ---")
    for u in test_urls:
        cleaned = validate_and_clean_url(u)
        print(f"{cleaned} -> {detect_url_type(cleaned)}")
        
    print("\n--- get_all_film_urls Test ---")
    test_list = "https://letterboxd.com/dave/watchlist/"
    urls = get_all_film_urls(test_list, page_range=(1, 2))
    print(f"Total deduplicated URLs found: {len(urls)}")
