# Input validation and import functions go here

import re
from urllib.parse import urlparse


LETTERBOXD_HOST = "letterboxd.com"


def validate_list_url(url: str) -> tuple[bool, str]:
    """
    Validate that the given string looks like a public Letterboxd list or
    watchlist URL.

    Returns:
        (True, normalised_url)  — if valid
        (False, error_message)  — if invalid
    """
    url = url.strip()

    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Could not parse the URL."

    # Must be letterboxd.com
    host = parsed.netloc.lower().lstrip("www.")
    if host != LETTERBOXD_HOST:
        return False, f"URL does not point to {LETTERBOXD_HOST} (got '{parsed.netloc}')."

    # Path must have at least 2 segments: /<username>/<list|watchlist>/
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return False, (
            "URL path is too short. Expected format: "
            "https://letterboxd.com/<username>/<list|watchlist>/..."
        )

    section = parts[1].lower()
    if section not in ("list", "watchlist", "lists"):
        return False, (
            f"Second path segment must be 'list' or 'watchlist', got '{parts[1]}'.\n"
            "Example: https://letterboxd.com/dave/list/official-top-250-narrative-feature-films/"
        )

    # Normalise: ensure trailing slash, drop query/fragment
    clean_path = "/" + "/".join(parts) + "/"
    normalised = f"https://{LETTERBOXD_HOST}{clean_path}"
    return True, normalised


def validate_output_format(fmt: str) -> tuple[bool, str]:
    """
    Validate the requested output format string.

    Returns:
        (True, normalised_fmt)  — 'csv' or 'json'
        (False, error_message)  — if unrecognised
    """
    fmt = fmt.strip().lower()
    if fmt in ("csv", "json"):
        return True, fmt
    return False, f"Unsupported output format '{fmt}'. Choose 'csv' or 'json'."


def validate_page_limit(value: str) -> tuple[bool, int | str]:
    """
    Validate the --pages argument is a positive integer.

    Returns:
        (True, int_value)       — if valid
        (False, error_message)  — if invalid
    """
    try:
        n = int(value)
        if n < 1:
            raise ValueError
        return True, n
    except (ValueError, TypeError):
        return False, f"Page limit must be a positive integer, got '{value}'."
