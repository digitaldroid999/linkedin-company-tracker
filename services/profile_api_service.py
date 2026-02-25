"""Fetch LinkedIn profile name from URL via RapidAPI get-profile-data-by-url."""

from __future__ import annotations

import requests
import time

from config.credentials import RAPIDAPI_KEY, RAPIDAPI_HOST

URL = "https://professional-network-data.p.rapidapi.com/get-profile-data-by-url"
HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
}


def _normalize_profile_url(url_or_slug: str) -> str:
    """Return full LinkedIn profile URL for API request."""
    s = (url_or_slug or "").strip()
    if not s:
        return ""
    if s.startswith("http") and "linkedin.com" in s and "/in/" in s:
        return s.split("?")[0].rstrip("/")
    if not s.startswith("http"):
        return f"https://www.linkedin.com/in/{s}"
    return s


def _format_name(first: str, last: str) -> str:
    """Format as '[firstName] [lastName]' with single space between."""
    return f"{first} {last}".strip()


def _extract_name_from_response(data: dict) -> str | None:
    """
    Extract display name from API response.
    Checks top-level and common nested paths (data, profile).
    """
    if not isinstance(data, dict):
        return None

    def get_from(obj: dict) -> str | None:
        first = (obj.get("firstName") or "").strip()
        last = (obj.get("lastName") or "").strip()
        if first or last:
            return _format_name(first, last)
        return None
    
    # Top-level firstName/lastName
    name = get_from(data)
    if name:
        return name
    # Common nested paths
    for key in ("data", "profile", "result"):
        child = data.get(key)
        if isinstance(child, dict):
            name = get_from(child)
            if name:
                return name
    return None


def get_profile_name(profile_url_or_slug: str) -> str | None:
    """
    Fetch profile data by URL and return the display name, or None on failure.
    Uses RapidAPI professional-network-data get-profile-data-by-url.
    """
    url = _normalize_profile_url(profile_url_or_slug)
    if not url or "/in/" not in url:
        return None
    max_retries = 12
    for attempt in range(max_retries):
        try:
            response = requests.get(
                URL,
                headers=HEADERS,
                params={"url": url},
                timeout=15,
            )
            
            # Check for 429 status code
            if response.status_code == 429:
                if attempt == max_retries - 1:  # Last attempt
                    print(f"Rate limit exceeded after {max_retries} attempts")
                    return None
                print(f"Rate limit hit (429). Retrying in 10 seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(10)
                continue  # Retry the request
                
            response.raise_for_status()
            data = response.json()
            break  # Success, exit retry loop
            
        except (requests.RequestException, ValueError) as e:
            if attempt == max_retries - 1:  # Last attempt
                print(f"Failed after {max_retries} attempts: {e}")
                return None
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in 10 seconds...")
            time.sleep(10)
            continue

    if not isinstance(data, dict):
        return None

    return _extract_name_from_response(data)
