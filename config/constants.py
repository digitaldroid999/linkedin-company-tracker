"""Application constants and sheet names."""

GOOGLE_SHEET_ID = "1eSMeDYvcPdoBw1UYNI7pAnKpCAscBbjxHL-ZJAf879k"
# GOOGLE_SHEET_ID = "1v4E8NPeqSj11iks1GVZ01eSNEBqkmBtvHEfaJEkMR8o"

SHEETS_LINK = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}"

SHEET_PROFILES = "Profiles"
SHEET_OVERALL = "Overall List of Currently Followed Companies"
SHEET_NEW_FOLLOWS = "New Follows"
SHEET_NEW_UNFOLLOWS = "New Unfollows"

PROFILES_HEADERS = ["Name", "LinkedIn Profile", "Initially Scraped"]
OVERALL_HEADERS = ["Company Name", "Follower Name", "Initial Scrape Date", "Date Followed", "Company URL", "Follower URL"]
NEW_FOLLOWS_HEADERS = ["Company Name", "Follower Name", "Date Followed", "Follower URL"]
NEW_UNFOLLOWS_HEADERS = ["Company Name", "Follower Name", "Initial Scrape Date", "Date Followed", "Unfollowed Date", "Follower URL"]

INITIALLY_SCRAPED_YES = "Yes"
INITIALLY_SCRAPED_NO = "No"

AUTO_SCRAPE_HOUR = 9
AUTO_SCRAPE_MINUTE = 0
SUMMARY_EMAIL = "mattcmcknight@gmail.com"
# LinkedIn URL patterns
LINKEDIN_PROFILE_BASE = "https://www.linkedin.com/in/"
LINKEDIN_COMPANY_BASE = "https://www.linkedin.com/company/"
