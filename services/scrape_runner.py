"""Orchestrates scraping all profiles and syncing with Google Sheets."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from config.constants import LINKEDIN_PROFILE_BASE
from services.sheets_service import SheetsService
from services.linkedin_scraper import get_followed_companies


def _get_username_from_profile_url(url_or_slug: str) -> str:
    s = (url_or_slug or "").strip().lower()
    if not s:
        return ""
    if s.startswith("http"):
        if "/in/" in s:
            s = s.split("/in/")[-1].split("/")[0].split("?")[0]
    return s

def _format_date(d: datetime | None) -> str:
    if d is None:
        d = datetime.now()
    return d.strftime("%Y-%m-%d")


def excel_serial_to_date(serial_number):
    """
    Convert Excel serial number to date string in YYYY-MM-DD format
    
    Args:
        serial_number: Excel serial date (e.g., 46077)
    
    Returns:
        String in YYYY-MM-DD format (e.g., "2026-02-24")
    """
    # Excel's epoch is 1899-12-30 (day 1)
    excel_epoch = datetime(1899, 12, 30)
    
    # Handle if serial_number is string or other type
    try:
        serial_number = float(serial_number)
    except (ValueError, TypeError):
        return str(serial_number)
    
    # Convert serial to date
    converted_date = excel_epoch + timedelta(days=serial_number)
    
    # Return in YYYY-MM-DD format
    return converted_date.strftime("%Y-%m-%d")


def run_scrape(
    on_status: Callable[[str], None] | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> tuple[int, int, int, list[dict], list[dict]]:
    """
    Scrapes all profiles from Sheets, updates Overall/New Follows/New Unfollows.
    on_status(message), on_progress(current_profile, new_follows_count, new_unfollows_count).
    Returns: (profiles_processed, new_follows_count, new_unfollows_count, new_follows_list, new_unfollows_list).
    """
    sheets = SheetsService()
    profiles = sheets.get_profiles()
    today = _format_date(datetime.now())
    new_follows_list: list[dict] = []
    new_unfollows_list: list[dict] = []
    profiles_processed = 0

    for profile_display, follower_name, initially_scraped in profiles:
        normalized = _get_username_from_profile_url(profile_display)
        if not normalized:
            continue
        follower_url = profile_display if profile_display.startswith("http") else f"{LINKEDIN_PROFILE_BASE}{normalized}/"
        display_name = (follower_name or "").strip() or follower_url
        if on_status:
            on_status(display_name)
        try:
            companies = get_followed_companies(profile_display)
        except Exception as e:
            if on_status:
                on_status(f"{display_name} (error: {e})")
            continue
        profiles_processed += 1

        is_initial = initially_scraped.strip().lower() != "yes"

        if is_initial:
            for c in companies:
                company_name = (c.get("name") or c.get("url", "")).strip()
                company_url = (c.get("url") or "").strip()
                sheets.append_overall(company_name, company_url, display_name, follower_url, today, "")
            sheets.set_profile_initially_scraped(profile_display)
        else:
            overall_set = sheets.get_overall_set()
            overall_records = sheets.get_overall_records()
            follower_key = _get_username_from_profile_url(follower_url)
            current_set: set[tuple[str, str]] = set()
            for c in companies:
                name = (c.get("name") or c.get("url", "")).strip()
                if name:
                    current_set.add((name.lower(), follower_key))

            # New follows: in current but not in overall
            for c in companies:
                company_name = (c.get("name") or c.get("url", "")).strip()
                company_url = (c.get("url") or "").strip()
                key = (company_name.lower(), follower_key)
                if key not in overall_set:
                    sheets.append_overall(company_name, company_url, display_name, follower_url, "", today)
                    sheets.append_new_follow(company_name, company_url, display_name, follower_url, today)
                    new_follows_list.append({
                        "Company Name": company_name,
                        "Company URL": company_url,
                        "Follower Name": display_name,
                        "Follower URL": follower_url,
                        "Date Followed": today,
                    })

            # New unfollows: in overall for this follower (by URL) but not in current
            rows_to_remove: list[int] = []
            for row_index, rec in enumerate(overall_records):
                rec_follower_key = _get_username_from_profile_url(rec.get("Follower URL", ""))
                if rec_follower_key != follower_key:
                    continue
                comp_key = (rec["Company Name"].strip().lower(), follower_key)
                if comp_key not in current_set:
                    sheets.append_new_unfollow(
                        rec["Company Name"],
                        rec.get("Company URL", ""),
                        display_name,
                        rec.get("Follower URL", ""),
                        rec.get("Initial Scrape Date", ""),
                        excel_serial_to_date(rec.get("Date Followed", "")),
                        today,
                    )
                    new_unfollows_list.append({
                        **rec,
                        "Unfollowed Date": today,
                    })
                    if row_index is not None:
                        rows_to_remove.append(row_index + 2)

            # Remove unfollowed rows from overall (from bottom to top to preserve indices)
            for row_index in sorted(rows_to_remove, reverse=True):
                sheets.remove_from_overall_by_row_index(row_index)

        if on_progress:
            on_progress(display_name, len(new_follows_list), len(new_unfollows_list))

    return profiles_processed, len(new_follows_list), len(new_unfollows_list), new_follows_list, new_unfollows_list
