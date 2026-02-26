"""Fetch followed companies for a LinkedIn profile via RapidAPI."""

from __future__ import annotations

import time
import requests

from config.credentials import RAPIDAPI_KEY, RAPIDAPI_HOST
from services.logging_service import get_logger

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
    logger = get_logger()
    username = _get_username_from_profile_url(profile_url_or_slug)
    if not username:
        return []

    results: list[dict] = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        payload = {"username": username, "page": page}
        data = None
        max_retries = 15
        for attempt in range(max_retries):
            try:
                for _ in range(12):
                    try:
                        response = requests.post(URL, json=payload, headers=HEADERS, timeout=10)
                        break
                    except Exception:
                        pass
                if response.status_code == 429:
                    # Rate limit: retry with backoff
                    if attempt == max_retries - 1:
                        logger.error(
                            "Rate limit (429) for username=%s page=%d after %d attempts",
                            username,
                            page,
                            max_retries,
                        )
                        raise LinkedInAPIError(
                            "Rate limit exceeded (429) after retries. " + API_ERROR_MESSAGE
                        )
                    logger.warning(
                        "Rate limit (429) for username=%s page=%d. Retrying in 10 seconds... (Attempt %d/%d)",
                        username,
                        page,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(10)
                    continue
                # Non-429: check for other HTTP errors
                response.raise_for_status()
                data = response.json()
                break
            except LinkedInAPIError:
                # Propagate LinkedInAPIError directly
                raise
            except (requests.RequestException, ValueError) as e:
                # Timeouts, connection errors, JSON errors, etc.
                if attempt == max_retries - 1:
                    logger.error(
                        "Request failed for username=%s page=%d after %d attempts: %s",
                        username,
                        page,
                        max_retries,
                        e,
                    )
                    if page == 1:
                        # Surface error to caller for first page
                        raise LinkedInAPIError(API_ERROR_MESSAGE) from e
                    # For subsequent pages, stop pagination gracefully
                    data = None
                    break
                logger.warning(
                    "Request attempt %d failed for username=%s page=%d: %s. Retrying in 10 seconds...",
                    attempt + 1,
                    username,
                    page,
                    e,
                )
                time.sleep(10)
        if data is None:
            # Either all retries failed or caller decided to stop pagination
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
        