"""Google Sheets read/write for Profiles, Overall list, New Follows, and New Unfollows."""

from __future__ import annotations

import gspread
import time
from google.oauth2.service_account import Credentials

from config.credentials import EMBEDDED_SERVICE_ACCOUNT
from config.constants import (
    GOOGLE_SHEET_ID,
    SHEET_PROFILES,
    SHEET_OVERALL,
    SHEET_NEW_FOLLOWS,
    SHEET_NEW_UNFOLLOWS,
    PROFILES_HEADERS,
    OVERALL_HEADERS,
    NEW_FOLLOWS_HEADERS,
    NEW_UNFOLLOWS_HEADERS,
    INITIALLY_SCRAPED_NO,
    INITIALLY_SCRAPED_YES,
)


def _parse_hyperlink_cell(cell_value: str) -> tuple[str, str]:
    """
    If cell_value is =HYPERLINK("url", "label") return (url, label).
    Label may contain escaped quotes "". Otherwise return ("", cell_value or "").
    =HYPERLINK("https://www.linkedin.com/in/gabriel-badiu-b11a79353/", "Gabriel Badiu")
    """
    s = (cell_value or "").strip()
    if not s.startswith("=HYPERLINK("):
        return ("", s)
    first_quote = s.find('"')
    if first_quote == -1:
        return ("", s)
    end_url = first_quote + 1
    while end_url < len(s) and s[end_url] != '"':
        end_url += 1
    url = s[first_quote + 1 : end_url]
    rest = s[end_url + 1 :].lstrip()
    if not rest.startswith(","):
        return (url, url)
    rest = rest[1:].lstrip()
    if not rest.startswith('"'):
        return (url, url)
    pos = 1
    while pos < len(rest):
        if rest[pos] == '"':
            if pos + 1 < len(rest) and rest[pos + 1] == '"':
                pos += 2
                continue
            break
        pos += 1
    label = rest[1:pos].replace('""', '"')
    return (url, label)


def _url_from_cell(cell_value: str) -> str:
    """Extract URL from a cell that may be =HYPERLINK("url", "label") or plain URL/text. Returns URL or original string."""
    url, _ = _parse_hyperlink_cell(cell_value)
    return url if url else (cell_value or "").strip()


def _normalize_profile_url(url_or_slug: str) -> str:
    s = (url_or_slug or "").strip().lower()
    if not s:
        return ""
    if s.startswith("http"):
        if "/in/" in s:
            s = s.split("/in/")[-1].split("/")[0].split("?")[0]
    return s


def _row_key(company: str, follower: str) -> tuple[str, str]:
    """Canonical key for (company, follower display name) to avoid duplicates."""
    return ((company or "").strip().lower(), (follower or "").strip().lower())


def _row_key_by_url(company: str, follower_url: str) -> tuple[str, str]:
    """Canonical key using company name and normalized follower profile URL."""
    return ((company or "").strip().lower(), _normalize_profile_url(follower_url or ""))


def _hyperlink_formula(url: str, label: str) -> str:
    """Build =HYPERLINK("url", "label") with escaped quotes."""
    url = (url or "").replace('"', '""')
    label = (label or "").replace('"', '""')
    return f'=HYPERLINK("{url}", "{label}")'


class SheetsService:
    """Handles all Google Sheets operations for the tracker."""

    def __init__(self) -> None:
        creds = Credentials.from_service_account_info(
            EMBEDDED_SERVICE_ACCOUNT,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._gc = gspread.authorize(creds)
        self._spreadsheet = self._gc.open_by_key(GOOGLE_SHEET_ID)

    def _sheet(self, name: str):
        return self._spreadsheet.worksheet(name)

    # ---------- Profiles ----------
    def get_profiles(self) -> list[tuple[str, str, str]]:
        """Returns list of (linkedin_profile, name, initially_scraped). Header row excluded."""
        ws = self._sheet(SHEET_PROFILES)
        rows = ws.get_all_values()
        if not rows or rows[0] != PROFILES_HEADERS:
            return []
        out = []
        for row in rows[1:]:
            name = (row[0].strip() if len(row) > 0 else "") or ""
            profile = (row[1].strip() if len(row) > 1 else "") or ""
            scraped = (row[2].strip() if len(row) > 2 else "") or ""
            if profile:
                out.append((profile, name, scraped))
        return out

    def get_profile_count(self) -> int:
        return len(self.get_profiles())

    def profile_exists(self, url_or_slug: str) -> bool:
        key = _normalize_profile_url(url_or_slug)
        if not key:
            return False
        for profile, _name, _ in self.get_profiles():
            if _normalize_profile_url(profile) == key:
                return True
        return False

    def add_profile(self, name: str, url_or_slug: str) -> bool:
        """Append profile (Name, LinkedIn Profile, Initially Scraped = No). Returns True if added."""
        normalized = _normalize_profile_url(url_or_slug)
        if not normalized:
            return False
        if self.profile_exists(url_or_slug):
            return False
        ws = self._sheet(SHEET_PROFILES)
        profile_display = url_or_slug.strip()
        if not profile_display.lower().startswith("http"):
            profile_display = f"https://www.linkedin.com/in/{normalized}"
        ws.append_row([(name or "").strip(), profile_display, INITIALLY_SCRAPED_NO])
        return True

    def get_profile_name(self, url_or_slug: str) -> str | None:
        """Return the Name (first column) for the profile matching url_or_slug, or None if not found."""
        key = _normalize_profile_url(url_or_slug)
        if not key:
            return None
        for profile, name, _ in self.get_profiles():
            if _normalize_profile_url(profile) == key:
                return (name or "").strip() or None
        return None

    def get_profile_url_by_name(self, name: str) -> str | None:
        """Return the LinkedIn Profile (column 2) for the first row where Name (column 1) matches, or None. Case-insensitive comparison."""
        name_key = (name or "").strip().lower()
        if not name_key:
            return None
        for profile, row_name, _ in self.get_profiles():
            if (row_name or "").strip().lower() == name_key:
                return profile
        return None

    def name_exists(self, name: str) -> bool:
        """Return True if any profile has Name matching the given name (case-insensitive)."""
        return self.get_profile_url_by_name(name) is not None

    def remove_profile(self, url_or_slug: str) -> bool:
        """Remove first matching profile by LinkedIn Profile. Returns True if removed."""
        key = _normalize_profile_url(url_or_slug)
        if not key:
            return False
        ws = self._sheet(SHEET_PROFILES)
        rows = ws.get_all_values()
        if not rows or rows[0] != PROFILES_HEADERS:
            return False
        for i in range(1, len(rows)):
            if _normalize_profile_url(rows[i][1] if len(rows[i]) > 1 else "") == key:
                ws.delete_rows(i + 1)
                return True
        return False

    def _delete_rows_where_follower_url_matches(self, sheet_name: str, profile_url_normalized: str, follower_cell_col: int = 2) -> int:
        """Delete all data rows where the follower cell (1-based) contains a URL that normalizes to profile_url_normalized. Parses HYPERLINK formulas. Returns count deleted."""
        ws = self._sheet(sheet_name)
        rows = ws.get_all_values(value_render_option='FORMULA')
        if not rows or len(rows) < 2:
            return 0
        to_delete = []
        for i in range(1, len(rows)):
            cell_val = rows[i][follower_cell_col - 1] if len(rows[i]) >= follower_cell_col else ""
            url = _parse_hyperlink_cell(cell_val)[0]
            if _normalize_profile_url(url) == profile_url_normalized:
                to_delete.append(i + 1)
        for row_index in sorted(to_delete, reverse=True):
            ws.delete_rows(row_index)
        return len(to_delete)

    def _resolve_to_profile_url(self, identifier: str) -> str | None:
        """Resolve an identifier (LinkedIn profile URL/slug or Name) to the profile URL, or None if not found."""
        identifier = (identifier or "").strip()
        if not identifier:
            return None
        if self.profile_exists(identifier):
            key = _normalize_profile_url(identifier)
            for profile, _name, _ in self.get_profiles():
                if _normalize_profile_url(profile) == key:
                    return profile
        return self.get_profile_url_by_name(identifier)

    def remove_profile_and_related_records(self, identifier: str) -> bool:
        """Remove profile from Profiles and all related rows in other sheets. identifier can be LinkedIn profile URL/slug or Name. Returns True if found and removed."""
        profile_url = self._resolve_to_profile_url(identifier)
        if not profile_url:
            return False
        key = _normalize_profile_url(profile_url)
        self.remove_profile(profile_url)
        self._delete_rows_where_follower_url_matches(SHEET_OVERALL, key, follower_cell_col=2)
        self._delete_rows_where_follower_url_matches(SHEET_NEW_FOLLOWS, key, follower_cell_col=2)
        self._delete_rows_where_follower_url_matches(SHEET_NEW_UNFOLLOWS, key, follower_cell_col=2)
        return True

    def set_profile_initially_scraped(self, url_or_slug: str) -> None:
        """Set Initially Scraped = Yes for the given profile."""
        key = _normalize_profile_url(url_or_slug)
        if not key:
            return
        ws = self._sheet(SHEET_PROFILES)
        rows = ws.get_all_values()
        for i in range(1, len(rows)):
            if _normalize_profile_url(rows[i][1] if len(rows[i]) > 1 else "") == key:
                ws.update_cell(i + 1, 3, INITIALLY_SCRAPED_YES)
                return

    # ---------- Overall list (efficient lookup) ----------
    def get_overall_records(self) -> list[dict]:
        """Returns list of dicts: Company Name, Company URL, Follower Name, Follower URL, Initial Scrape Date, Date Followed. Parses HYPERLINK formulas in cells."""
        ws = self._sheet(SHEET_OVERALL)
        rows = ws.get_all_values(value_render_option='FORMULA')
        if not rows or (rows[0][:4] if len(rows[0]) >= 4 else rows[0]) != OVERALL_HEADERS[:4]:
            return []
        out = []
        for row in rows[1:]:
            if len(row) < 2:
                continue
            company_url, company_name = _parse_hyperlink_cell(row[0] or "")
            follower_url, follower_name = _parse_hyperlink_cell(row[1] or "")
            if not company_name and not company_url:
                company_name = (row[0] or "").strip()
            if not follower_name and not follower_url:
                follower_name = (row[1] or "").strip()
            if company_name or company_url or follower_name or follower_url:
                out.append({
                    "Company Name": company_name,
                    "Company URL": company_url,
                    "Follower Name": follower_name,
                    "Follower URL": follower_url,
                    "Initial Scrape Date": row[2] if len(row) > 2 else "",
                    "Date Followed": row[3] if len(row) > 3 else "",
                })
        return out

    def get_overall_set(self) -> set[tuple[str, str]]:
        """Set of (company_name, normalized_follower_url) for fast membership check."""
        records = self.get_overall_records()
        return records, {_row_key_by_url(r["Company Name"], r.get("Follower URL", "")) for r in records}

    def append_overall(
        self,
        company_name: str,
        company_url: str,
        follower_name: str,
        follower_url: str,
        initial_scrape_date: str,
        date_followed: str,
    ) -> None:
        """Append a single overall record (legacy helper). Prefer append_overall_batch when adding many rows."""
        self.append_overall_batch(
            [
                (
                    company_name,
                    company_url,
                    follower_name,
                    follower_url,
                    initial_scrape_date,
                    date_followed,
                )
            ]
        )

    def append_overall_batch(
        self,
        records: list[tuple[str, str, str, str, str, str]],
    ) -> None:
        """Append multiple overall records in a single Sheets API call.

        Each record is (company_name, company_url, follower_name, follower_url, initial_scrape_date, date_followed).
        """
        if not records:
            return
        ws = self._sheet(SHEET_OVERALL)
        values: list[list[str]] = []
        for (
            company_name,
            company_url,
            follower_name,
            follower_url,
            initial_scrape_date,
            date_followed,
        ) in records:
            company_cell = _hyperlink_formula(company_url, company_name) if company_url else company_name
            follower_cell = _hyperlink_formula(follower_url, follower_name) if follower_url else follower_name
            values.append([company_cell, follower_cell, initial_scrape_date, date_followed])
        # Use append_rows to minimize per-row API calls.
        ws.append_rows(values, value_input_option="USER_ENTERED")

    def remove_from_overall_by_row_index(self, one_based_row: int) -> None:
        """Remove a single row from Overall sheet (1-based row number)."""
        self._sheet(SHEET_OVERALL).delete_rows(one_based_row)

    def find_overall_row_index(self, company_name: str, follower_url: str) -> int | None:
        """Returns 1-based row index in Overall sheet, or None. Matches by company name and normalized Follower URL. Parses HYPERLINK cells."""
        key = _row_key_by_url(company_name, follower_url)
        ws = self._sheet(SHEET_OVERALL)
        rows = ws.get_all_values()
        for i in range(1, len(rows)):
            if len(rows[i]) < 2:
                continue
            if _row_key_by_url(rows[i][0], rows[i][1]) == key:
                return i + 1
        return None

    # ---------- New Follows ----------
    def append_new_follow(
        self,
        company_name: str,
        company_url: str,
        follower_name: str,
        follower_url: str,
        date_followed: str,
    ) -> None:
        """Append a single new-follow record (legacy helper). Prefer append_new_follows_batch when adding many rows."""
        self.append_new_follows_batch(
            [(company_name, company_url, follower_name, follower_url, date_followed)]
        )

    def append_new_follows_batch(
        self,
        records: list[tuple[str, str, str, str, str]],
    ) -> None:
        """Append multiple new-follow records in a single Sheets API call.

        Each record is (company_name, company_url, follower_name, follower_url, date_followed).
        """
        if not records:
            return
        ws = self._sheet(SHEET_NEW_FOLLOWS)
        values: list[list[str]] = []
        for company_name, company_url, follower_name, follower_url, date_followed in records:
            company_cell = _hyperlink_formula(company_url, company_name) if company_url else company_name
            follower_cell = _hyperlink_formula(follower_url, follower_name) if follower_url else follower_name
            values.append([company_cell, follower_cell, date_followed])
        ws.append_rows(values, value_input_option="USER_ENTERED")

    # ---------- New Unfollows ----------
    def append_new_unfollow(
        self,
        company_name: str,
        company_url: str,
        follower_name: str,
        follower_url: str,
        initial_scrape_date: str,
        date_followed: str,
        unfollowed_date: str,
    ) -> None:
        """Append a single new-unfollow record (legacy helper). Prefer append_new_unfollows_batch when adding many rows."""
        self.append_new_unfollows_batch(
            [
                (
                    company_name,
                    company_url,
                    follower_name,
                    follower_url,
                    initial_scrape_date,
                    date_followed,
                    unfollowed_date,
                )
            ]
        )

    def append_new_unfollows_batch(
        self,
        records: list[tuple[str, str, str, str, str, str, str]],
    ) -> None:
        """Append multiple new-unfollow records in a single Sheets API call.

        Each record is (company_name, company_url, follower_name, follower_url, initial_scrape_date, date_followed, unfollowed_date).
        """
        if not records:
            return
        ws = self._sheet(SHEET_NEW_UNFOLLOWS)
        values: list[list[str]] = []
        for (
            company_name,
            company_url,
            follower_name,
            follower_url,
            initial_scrape_date,
            date_followed,
            unfollowed_date,
        ) in records:
            company_cell = _hyperlink_formula(company_url, company_name) if company_url else company_name
            follower_cell = _hyperlink_formula(follower_url, follower_name) if follower_url else follower_name
            values.append([company_cell, follower_cell, initial_scrape_date, date_followed, unfollowed_date])
        ws.append_rows(values, value_input_option="USER_ENTERED")
