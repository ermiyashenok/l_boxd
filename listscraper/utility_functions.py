# Utility helper functions go here

from bs4 import BeautifulSoup

LETTERBOXD_BASE = "https://letterboxd.com"


# ──────────────────────────────────────────────────────────────────────────────
# URL builders
# ──────────────────────────────────────────────────────────────────────────────

def build_film_url(slug: str) -> str:
    """
    Convert a film slug (e.g. 'parasite-2019') to a full Letterboxd URL.

    Example:
        build_film_url("parasite-2019")
        → "https://letterboxd.com/film/parasite-2019/"
    """
    slug = slug.strip("/")
    return f"{LETTERBOXD_BASE}/film/{slug}/"


def build_histogram_url(film_url: str) -> str:
    """
    Return the ESI rating-histogram URL for a given film page URL.

    The ESI endpoint returns a clean HTML fragment with per-half-star
    counts in <li data-count="N"> elements.

    Example:
        build_histogram_url("https://letterboxd.com/film/parasite-2019/")
        → "https://letterboxd.com/esi/film/parasite-2019/rating-histogram/"
    """
    # Strip base, keep the /film/<slug>/ portion
    path = film_url.replace(LETTERBOXD_BASE, "").strip("/")
    return f"{LETTERBOXD_BASE}/esi/{path}/rating-histogram/"


def build_details_url(film_url: str) -> str:
    """
    Return the /details/ URL for a given film page URL.
    Useful for extracting crew/cast when the main page lazy-loads them.

    Example:
        build_details_url("https://letterboxd.com/film/parasite-2019/")
        → "https://letterboxd.com/film/parasite-2019/details/"
    """
    return film_url.rstrip("/") + "/details/"


def extract_slug_from_url(url: str) -> str:
    """
    Extracts the slug from a film URL.
    
    Example:
        extract_slug_from_url("https://letterboxd.com/film/parasite-2019/")
        → "parasite-2019"
    """
    return url.rstrip("/").split("/")[-1]


# ──────────────────────────────────────────────────────────────────────────────
# Rating histogram parser
# ──────────────────────────────────────────────────────────────────────────────

# Ordered rating keys matching Letterboxd's half-star increments (0.5 → 5.0)
RATING_KEYS = [
    "half", "one", "one_half",
    "two", "two_half",
    "three", "three_half",
    "four", "four_half",
    "five",
]


def parse_rating_histogram(html: str) -> dict[str, int]:
    """
    Parse the ESI rating-histogram HTML fragment and return a dictionary
    mapping each half-star rating to its integer count.

    The histogram fragment contains <li> elements with a ``data-count``
    attribute ordered from 0.5 stars to 5 stars.

    Args:
        html: Raw HTML string of the histogram fragment.

    Returns:
        dict with keys: half, one, one_half, two, two_half,
                        three, three_half, four, four_half, five.
        Missing bins default to 0.
    """
    soup = BeautifulSoup(html, "lxml")

    histogram: dict[str, int] = {key: 0 for key in RATING_KEYS}

    items = soup.find_all("li", attrs={"data-count": True})

    for index, li in enumerate(items):
        if index >= len(RATING_KEYS):
            break
        try:
            count = int(li["data-count"])
        except (ValueError, KeyError):
            count = 0
        histogram[RATING_KEYS[index]] = count

    return histogram


# ──────────────────────────────────────────────────────────────────────────────
# Output helpers
# ──────────────────────────────────────────────────────────────────────────────

import csv
import json
import os
from datetime import datetime


def make_output_filename(list_url: str, fmt: str, output_dir: str = "scraper_outputs") -> str:
    """
    Build an output filename based on the list URL and current timestamp.

    Example:
        make_output_filename("https://letterboxd.com/dave/list/top-250/", "csv")
        → "scraper_outputs/dave_top-250_20240515_143022.csv"
    """
    from urllib.parse import urlparse
    parts = [p for p in urlparse(list_url).path.strip("/").split("/") if p]
    # parts: [username, 'list', list-name] or [username, 'watchlist']
    username = parts[0] if parts else "unknown"
    listname = parts[-1] if len(parts) > 1 else "list"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{username}_{listname}_{timestamp}.{fmt}"
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, filename)


def save_csv(films: list[dict], filepath: str) -> None:
    """
    Write a list of film dicts to a CSV file.

    Flattens the 'cast' list to a semicolon-separated string.
    Skips None entries silently.
    """
    films = [f for f in films if f is not None]
    if not films:
        print("Warning: no film data to save.")
        return

    # Build a flat fieldname list from the union of all keys
    fieldnames = list(dict.fromkeys(k for f in films for k in f.keys()))

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for film in films:
            row = dict(film)
            # Flatten list fields
            if isinstance(row.get("cast"), list):
                row["cast"] = "; ".join(row["cast"])
            if isinstance(row.get("rating_histogram"), dict):
                row["rating_histogram"] = json.dumps(row["rating_histogram"])
            writer.writerow(row)

    print(f"Saved {len(films)} films → {filepath}")


def save_json(films: list[dict], filepath: str) -> None:
    """
    Write a list of film dicts to a pretty-printed JSON file.
    Skips None entries silently.
    """
    films = [f for f in films if f is not None]
    if not films:
        print("Warning: no film data to save.")
        return

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(films, fh, ensure_ascii=False, indent=2)

    print(f"Saved {len(films)} films → {filepath}")

