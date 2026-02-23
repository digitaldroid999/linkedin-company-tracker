"""Send summary email after scraping (using SMTP or a simple approach)."""

from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.constants import SUMMARY_EMAIL, SHEETS_LINK

def build_summary_html(
    profiles_processed: int,
    new_follows_count: int,
    new_unfollows_count: int,
    new_follows_list: list[dict],
    new_unfollows_list: list[dict],
) -> str:
    """Build HTML email body with clickable LinkedIn links."""
    def link(url: str, text: str) -> str:
        return f'<a href="{url}" style="color:#0A66C2;">{text}</a>'

    lines = [
        "<h2>LinkedIn Company Tracker – Scrape Summary</h2>",
        f"<p><b>Profiles processed:</b> {profiles_processed}</p>",
        f"<p><b>New follows:</b> {new_follows_count}</p>",
        f"<p><b>New unfollows:</b> {new_unfollows_count}</p>",
        "<p><a href=\"" + SHEETS_LINK + "\">Open tracking spreadsheet</a></p>",
    ]
    if new_follows_list:
        lines.append("<h3>New follows</h3><ul>")
        for r in new_follows_list:
            company = r.get("Company Name", "")
            follower = r.get("Follower Name", "")
            date_f = r.get("Date Followed", "")
            company_url = r.get("Company URL", "")
            follower_url = r.get("Follower URL", "") or (follower if follower.startswith("http") else "")
            company_part = link(company_url, company) if company_url else company
            follower_part = link(follower_url, follower) if follower_url else follower
            lines.append(
                f"<li>Company: {company_part} | "
                f"Follower: {follower_part} | {date_f}</li>"
            )
        lines.append("</ul>")
    if new_unfollows_list:
        lines.append("<h3>New unfollows</h3><ul>")
        for r in new_unfollows_list:
            company = r.get("Company Name", "")
            follower = r.get("Follower Name", "")
            unfollowed = r.get("Unfollowed Date", "")
            company_url = r.get("Company URL", "")
            follower_url = r.get("Follower URL", "") or (follower if follower.startswith("http") else "")
            company_part = link(company_url, company) if company_url else company
            follower_part = link(follower_url, follower) if follower_url else follower
            lines.append(
                f"<li>Company: {company_part} | "
                f"Follower: {follower_part} | Unfollowed: {unfollowed}</li>"
            )
        lines.append("</ul>")
    return "<br>\n".join(lines)


def send_summary_email(
    profiles_processed: int,
    new_follows_count: int,
    new_unfollows_count: int,
    new_follows_list: list[dict],
    new_unfollows_list: list[dict],
    smtp_server: str | None = None,
    smtp_port: int = 587,
    sender_email: str | None = None,
    sender_password: str | None = None,
) -> tuple[bool, str]:
    """
    Send summary to SUMMARY_EMAIL. Uses sender_email/sender_password (e.g. Gmail app password).
    Can be set via env TRACKER_SENDER_EMAIL and TRACKER_SENDER_PASSWORD.
    Returns (success, message).
    """
    sender_email = sender_email or os.environ.get("TRACKER_SENDER_EMAIL", "")
    sender_password = sender_password or os.environ.get("TRACKER_SENDER_PASSWORD", "")
    if not sender_email or not sender_password:
        return False, "Email not configured: set TRACKER_SENDER_EMAIL and TRACKER_SENDER_PASSWORD (e.g. Gmail app password) in environment or Settings."
    html = build_summary_html(
        profiles_processed, new_follows_count, new_unfollows_count,
        new_follows_list, new_unfollows_list,
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "LinkedIn Company Tracker – Scrape Summary"
    msg["From"] = sender_email
    msg["To"] = SUMMARY_EMAIL
    msg.attach(MIMEText(html, "html"))
    print(msg.as_string())
    try:
        server = smtplib.SMTP(smtp_server or "smtp.gmail.com", smtp_port or 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, SUMMARY_EMAIL, msg.as_string())
        server.quit()
        return True, "Summary email sent."
    except Exception as e:
        return False, str(e)
