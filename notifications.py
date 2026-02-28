"""
Desktop and email notification helpers.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_desktop_notification(title: str, message: str) -> None:
    """Cross-platform desktop notification via plyer."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="SkySync",
            timeout=12,
        )
    except Exception as e:
        print(f"[Notify] Desktop notification failed: {e}")


def send_email_alert(
    to_email: str,
    tracker_name: str,
    price: float,
    currency: str,
    booking_url: str,
) -> None:
    """Send an HTML email alert when a price target is hit."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        print("[Notify] SMTP not configured — skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"✈ SkySync: {tracker_name} is now {currency} {price:,.0f}"
    msg["From"] = smtp_user
    msg["To"] = to_email

    html = f"""
    <html>
    <body style="font-family:sans-serif;background:#0d1117;color:#e6edf3;padding:32px;">
      <div style="max-width:480px;margin:0 auto;background:#161b22;border-radius:12px;
                  border:1px solid #f59e0b;padding:32px;">
        <h1 style="color:#f59e0b;margin:0 0 8px">✈ Flight Price Alert</h1>
        <p style="color:#8b949e;margin:0 0 24px">SkySync detected a price drop on your tracked route.</p>
        <h2 style="margin:0 0 4px">{tracker_name}</h2>
        <p style="font-size:2rem;color:#f59e0b;margin:0 0 24px;font-weight:bold;">
          {currency} {price:,.2f}
        </p>
        <a href="{booking_url}"
           style="background:#f59e0b;color:#000;padding:12px 24px;border-radius:6px;
                  text-decoration:none;font-weight:bold;display:inline-block;">
          Book Now →
        </a>
        <p style="color:#8b949e;font-size:0.8rem;margin-top:24px;">
          Sent by SkySync · Unsubscribe by removing your email from the tracker.
        </p>
      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        print(f"[Notify] Email sent to {to_email}")
    except Exception as e:
        print(f"[Notify] Email failed: {e}")
