# LinkedIn Company Tracker

Desktop app to track company follows/unfollows for a list of LinkedIn profiles, with sync to a Google Sheet.

## Setup

1. **Python 3.10+** and a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Google Sheet**: Ensure the spreadsheet exists and has these 4 sheets with exact names and headers:

   - **Profiles**: `User Profile` | `Initially Scraped`
   - **Overall List of Currently Followed Companies**: `Company Name` | `Follower Name` | `Initial Scrape Date` | `Date Followed`
   - **New Follows**: `Company Name` | `Follower Name` | `Date Followed`
   - **New Unfollows**: `Company Name` | `Follower Name` | `Initial Scrape Date` | `Date Followed` | `Unfollowed Date`

   Share the spreadsheet with the service account email (see `config/credentials.py`) with Editor access.

3. **Optional – email summary**: To receive the scrape summary by email, set:

   - `TRACKER_SENDER_EMAIL`: your Gmail (or other SMTP) address
   - `TRACKER_SENDER_PASSWORD`: Gmail app password or account password

   Then check “Email me the scrape summary when finished” in Settings.

## Run

```bash
python main.py
```

- **Add/Remove**: Enter a LinkedIn profile URL (e.g. `https://www.linkedin.com/in/john-doe/`) or username and click Add or Remove.
- **Run**: Scrapes all profiles and updates the sheet (new follows, new unfollows).
- **Auto-scrape**: Choose weekdays for 9:00 AM local time; the app runs in the background and triggers at that time on selected days.

## Notes

- Company interests are fetched via the RapidAPI “professional-network-data” API. Set `RAPIDAPI_KEY` in the environment to override the default key in `config/credentials.py`.
- Do not close the app while a run is in progress; the status bar shows “Scraping …” and the Run button stays disabled until finished.
