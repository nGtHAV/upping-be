"""
SMTP email notification module for UpPing.
Sends alert emails when sites go DOWN or come back UP.
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@upping.dev")
SMTP_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)


def send_alert_email(to_email: str, site_name: str, site_url: str, status: str,
                     error_msg: str | None = None, response_time: int = 0) -> bool:
    """Send an alert email for a site status change. Returns True on success."""
    if not SMTP_ENABLED:
        logger.debug("SMTP not configured, skipping email for %s", site_name)
        return False

    is_down = status == "DOWN"
    subject = f"🔴 {site_name} is DOWN" if is_down else f"🟢 {site_name} is back UP"

    # Build HTML body
    status_color = "#ba1a1a" if is_down else "#006948"
    status_label = "OFFLINE" if is_down else "RECOVERED"
    detail_section = ""
    if is_down and error_msg:
        detail_section = f'<tr><td style="padding:8px 0;color:#6d7a72;font-size:13px;">Error</td><td style="padding:8px 0;font-size:13px;">{error_msg}</td></tr>'

    html = f"""
    <div style="font-family:'Inter',system-ui,sans-serif;max-width:560px;margin:0 auto;background:#f8f9ff;padding:32px;">
      <div style="text-align:center;margin-bottom:24px;">
        <h1 style="font-size:18px;font-weight:800;letter-spacing:-0.5px;margin:0;">UpPing</h1>
        <p style="font-size:10px;text-transform:uppercase;letter-spacing:2px;color:#6d7a72;margin:4px 0 0;">Alert Notification</p>
      </div>
      <div style="background:#fff;border-radius:12px;padding:28px;box-shadow:0 2px 8px rgba(13,28,46,0.06);">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;">
          <div style="width:40px;height:40px;border-radius:10px;background:{status_color}15;display:flex;align-items:center;justify-content:center;">
            <span style="font-size:20px;">{'❌' if is_down else '✅'}</span>
          </div>
          <div>
            <h2 style="margin:0;font-size:16px;font-weight:600;">{site_name}</h2>
            <p style="margin:2px 0 0;font-size:12px;color:#6d7a72;">{site_url}</p>
          </div>
        </div>
        <div style="background:{status_color}10;border-left:4px solid {status_color};border-radius:8px;padding:16px;margin-bottom:20px;">
          <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{status_color};">{status_label}</span>
        </div>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px 0;color:#6d7a72;font-size:13px;">Response Time</td><td style="padding:8px 0;font-size:13px;">{response_time}ms</td></tr>
          {detail_section}
        </table>
      </div>
      <p style="text-align:center;font-size:10px;color:#6d7a72;margin-top:20px;">This is an automated alert from UpPing Monitoring. Do not reply.</p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info("Alert email sent to %s for %s (%s)", to_email, site_name, status)
        return True
    except Exception as e:
        logger.error("Failed to send alert email to %s: %s", to_email, e)
        return False
