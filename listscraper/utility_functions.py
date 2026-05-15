# Utility helper functions go here

from bs4 import BeautifulSoup
import csv
import json
import os
from datetime import datetime

LETTERBOXD_BASE = "https://letterboxd.com"


# ──────────────────────────────────────────────────────────────────────────────
# URL builders
# ──────────────────────────────────────────────────────────────────────────────

def build_film_url(slug: str) -> str:
    """
    Convert a film slug (e.g. 'parasite-2019') to a full Letterboxd URL.
    """
    slug = slug.strip("/")
    return f"{LETTERBOXD_BASE}/film/{slug}/"


def build_histogram_url(film_url: str) -> str:
    """
    Return the ESI rating-histogram URL for a given film page URL.
    """
    path = film_url.replace(LETTERBOXD_BASE, "").strip("/")
    return f"{LETTERBOXD_BASE}/esi/{path}/rating-histogram/"


def build_details_url(film_url: str) -> str:
    """
    Return the /details/ URL for a given film page URL.
    """
    return film_url.rstrip("/") + "/details/"


def extract_slug_from_url(url: str) -> str:
    """
    Extracts the slug from a film URL.
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
    Parse the ESI rating-histogram HTML fragment and return a dictionary.
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

def make_output_filename(list_url: str, fmt: str, output_dir: str = "scraper_outputs") -> str:
    """
    Build an output filename based on the list URL and current timestamp.
    """
    from urllib.parse import urlparse
    parts = [p for p in urlparse(list_url).path.strip("/").split("/") if p]
    username = parts[0] if parts else "unknown"
    listname = parts[-1] if len(parts) > 1 else "list"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{username}_{listname}_{timestamp}.{fmt}"
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, filename)


def save_to_csv(films: list[dict], output_path: str, output_name: str) -> None:
    os.makedirs(output_path, exist_ok=True)
    filepath = os.path.join(output_path, f"{output_name}.csv")
    
    if not films:
        print("Warning: No films to save.")
        return

    fieldnames = [
        "title", "year", "director", "cast", "average_rating", "rating_count",
        "fan_count", "half", "one", "one_half", "two", "two_half",
        "three", "three_half", "four", "four_half", "five", "letterboxd_url"
    ]
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        
        for film in films:
            if not film:
                continue
            row = film.copy()
            
            if isinstance(row.get("cast"), list):
                row["cast"] = "|".join(row["cast"])
                
            hist = row.get("rating_histogram") or {}
            for k in RATING_KEYS:
                row[k] = hist.get(k, 0)
                if row[k] is None:
                    row[k] = 0
                    
            writer.writerow(row)
            
    print(f"Saved CSV to {filepath}")


def save_to_json(films: list[dict], output_path: str, output_name: str) -> None:
    os.makedirs(output_path, exist_ok=True)
    filepath = os.path.join(output_path, f"{output_name}.json")
    
    if not films:
        print("Warning: No films to save.")
        return
        
    valid_films = [f for f in films if f]
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(valid_films, f, indent=2, ensure_ascii=False)
        
    print(f"Saved JSON to {filepath}")


def concat_films(list_of_film_lists: list[list[dict]]) -> list[dict]:
    """
    Takes a list of lists of film dictionaries.
    Flattens them and deduplicates by letterboxd_url.
    """
    flattened = []
    seen = set()
    
    for sublist in list_of_film_lists:
        for film in sublist:
            if film and film.get("letterboxd_url"):
                url = film["letterboxd_url"]
                if url not in seen:
                    seen.add(url)
                    flattened.append(film)
    return flattened
