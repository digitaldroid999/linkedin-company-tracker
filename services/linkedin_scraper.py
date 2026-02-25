"""Fetch followed companies for a LinkedIn profile via RapidAPI."""

from __future__ import annotations

import time
import requests

from config.credentials import RAPIDAPI_KEY, RAPIDAPI_HOST

URL = "https://professional-network-data.p.rapidapi.com/profiles/interests/companies"
HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
    "Content-Type": "application/json",
}

API_ERROR_MESSAGE = (
    "There was a problem with the API request. Please check your RapidAPI key status, "
    "subscription, and quota at https://rapidapi.com."
)


class LinkedInAPIError(Exception):
    """Raised when the API returns an error that the user should be notified about (e.g. 429, invalid key)."""
    pass


def _get_username_from_profile_url(url_or_slug: str) -> str:
    s = (url_or_slug or "").strip().lower()
    if not s:
        return ""
    if s.startswith("http") and "/in/" in s:
        s = s.split("/in/")[-1].split("/")[0].split("?")[0]
    return s


def get_followed_companies(profile_url_or_slug: str) -> list[dict]:
    """
    Returns list of dicts: {"name": str, "url": str} for each followed company.
    Uses RapidAPI professional-network-data profiles/interests/companies.
    """
    username = _get_username_from_profile_url(profile_url_or_slug)
    if not username:
        return []

    results: list[dict] = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        payload = {"username": username, "page": page}
        try:
            response = requests.post(URL, json=payload, headers=HEADERS, timeout=30)
            if response.status_code == 429:
                for attempt in range(12):
                    time.sleep(10)
                    response = requests.post(URL, json=payload, headers=HEADERS, timeout=30)
                    if response.status_code != 429:
                        break
                if response.status_code == 429:
                    raise LinkedInAPIError(
                        "Rate limit exceeded (429) after 12 retries. " + API_ERROR_MESSAGE
                    )
            response.raise_for_status()
            data = response.json()
        except LinkedInAPIError:
            raise
        except requests.RequestException as e:
            if page == 1:
                raise LinkedInAPIError(API_ERROR_MESSAGE) from e
            break
        except ValueError as e:
            if page == 1:
                raise LinkedInAPIError(API_ERROR_MESSAGE) from e
            break
        
        if not data.get("success"):
            if page == 1:
                return []
            break

        body = data.get("data") or {}
        items = body.get("items") or []
        total_pages = body.get("totalPages") or 1

        for item in items:
            name = (item.get("name") or "").strip()
            linkedin_url = (item.get("linkedinURL") or "").strip()
            if name or linkedin_url:
                results.append({
                    "name": name or linkedin_url,
                    "url": linkedin_url or "",
                })

        page += 1

    return results
