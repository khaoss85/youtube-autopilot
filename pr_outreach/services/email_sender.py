"""
Email Sender Service - Send outreach emails.

Supports:
- SendGrid API
- Mailgun API
- SMTP fallback
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, Tuple
from datetime import datetime
from yt_autopilot.core.logger import logger, log_fallback

import requests


def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    track_opens: bool = True,
    track_clicks: bool = False
) -> Tuple[bool, str, Optional[str]]:
    """
    Send an email using available provider.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body (plain text)
        from_email: Sender email (default from env)
        from_name: Sender name
        reply_to: Reply-to address
        track_opens: Enable open tracking
        track_clicks: Enable click tracking

    Returns:
        Tuple of (success, message_id_or_error, provider_used)
    """
    logger.info(f"Sending email to: {to_email}")
    logger.info(f"  Subject: {subject[:50]}...")

    # Set defaults from environment
    from_email = from_email or os.getenv("OUTREACH_FROM_EMAIL")
    from_name = from_name or os.getenv("OUTREACH_FROM_NAME", "")

    if not from_email:
        return (False, "No from_email configured", None)

    # Try SendGrid first
    sendgrid_key = os.getenv("SENDGRID_API_KEY")
    if sendgrid_key:
        success, result = _send_via_sendgrid(
            sendgrid_key, to_email, subject, body,
            from_email, from_name, reply_to,
            track_opens, track_clicks
        )
        if success:
            logger.info(f"  ✓ Sent via SendGrid: {result}")
            return (True, result, "sendgrid")
        else:
            logger.warning(f"  ✗ SendGrid failed: {result}")

    # Try Mailgun
    mailgun_key = os.getenv("MAILGUN_API_KEY")
    mailgun_domain = os.getenv("MAILGUN_DOMAIN")
    if mailgun_key and mailgun_domain:
        success, result = _send_via_mailgun(
            mailgun_key, mailgun_domain, to_email, subject, body,
            from_email, from_name, reply_to,
            track_opens, track_clicks
        )
        if success:
            logger.info(f"  ✓ Sent via Mailgun: {result}")
            return (True, result, "mailgun")
        else:
            logger.warning(f"  ✗ Mailgun failed: {result}")

    # Try SMTP fallback
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    if smtp_host and smtp_user and smtp_pass:
        success, result = _send_via_smtp(
            smtp_host, smtp_user, smtp_pass,
            to_email, subject, body, from_email, from_name, reply_to
        )
        if success:
            logger.info(f"  ✓ Sent via SMTP")
            return (True, result, "smtp")
        else:
            logger.warning(f"  ✗ SMTP failed: {result}")

    # All methods failed
    log_fallback(
        component="EMAIL_SENDER",
        fallback_type="ALL_PROVIDERS_FAILED",
        reason="No email provider available or all failed",
        impact="CRITICAL"
    )
    return (False, "No email provider available", None)


def _send_via_sendgrid(
    api_key: str,
    to_email: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str,
    reply_to: Optional[str],
    track_opens: bool,
    track_clicks: bool
) -> Tuple[bool, str]:
    """Send email via SendGrid API."""
    try:
        url = "https://api.sendgrid.com/v3/mail/send"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "personalizations": [{
                "to": [{"email": to_email}],
                "subject": subject
            }],
            "from": {
                "email": from_email,
                "name": from_name
            },
            "content": [{
                "type": "text/plain",
                "value": body
            }],
            "tracking_settings": {
                "open_tracking": {"enable": track_opens},
                "click_tracking": {"enable": track_clicks}
            }
        }

        if reply_to:
            data["reply_to"] = {"email": reply_to}

        response = requests.post(url, json=data, headers=headers, timeout=30)

        if response.status_code in [200, 201, 202]:
            # Get message ID from headers
            message_id = response.headers.get("X-Message-Id", f"sg_{datetime.now().timestamp()}")
            return (True, message_id)
        else:
            return (False, f"Status {response.status_code}: {response.text}")

    except Exception as e:
        return (False, str(e))


def _send_via_mailgun(
    api_key: str,
    domain: str,
    to_email: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str,
    reply_to: Optional[str],
    track_opens: bool,
    track_clicks: bool
) -> Tuple[bool, str]:
    """Send email via Mailgun API."""
    try:
        url = f"https://api.mailgun.net/v3/{domain}/messages"

        auth = ("api", api_key)

        data = {
            "from": f"{from_name} <{from_email}>" if from_name else from_email,
            "to": to_email,
            "subject": subject,
            "text": body,
            "o:tracking-opens": "yes" if track_opens else "no",
            "o:tracking-clicks": "yes" if track_clicks else "no"
        }

        if reply_to:
            data["h:Reply-To"] = reply_to

        response = requests.post(url, auth=auth, data=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            message_id = result.get("id", f"mg_{datetime.now().timestamp()}")
            return (True, message_id)
        else:
            return (False, f"Status {response.status_code}: {response.text}")

    except Exception as e:
        return (False, str(e))


def _send_via_smtp(
    host: str,
    user: str,
    password: str,
    to_email: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str,
    reply_to: Optional[str]
) -> Tuple[bool, str]:
    """Send email via SMTP."""
    try:
        port = int(os.getenv("SMTP_PORT", "587"))

        msg = MIMEMultipart()
        msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        msg["To"] = to_email
        msg["Subject"] = subject

        if reply_to:
            msg["Reply-To"] = reply_to

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        return (True, f"smtp_{datetime.now().timestamp()}")

    except Exception as e:
        return (False, str(e))


def check_email_status(message_id: str, provider: str) -> Dict:
    """
    Check status of a sent email.

    Returns dict with delivery status, opens, clicks.
    """
    result = {
        "delivered": None,
        "opened": None,
        "clicked": None,
        "bounced": None,
        "error": None
    }

    if provider == "sendgrid":
        # Would need SendGrid events API
        pass
    elif provider == "mailgun":
        # Would need Mailgun events API
        pass

    return result


def get_sending_quota() -> Dict:
    """Get remaining sending quota from provider."""
    quota = {
        "provider": None,
        "daily_limit": 0,
        "remaining": 0,
        "reset_at": None
    }

    # Check SendGrid
    sendgrid_key = os.getenv("SENDGRID_API_KEY")
    if sendgrid_key:
        quota["provider"] = "sendgrid"
        quota["daily_limit"] = 100  # Free tier default
        quota["remaining"] = 100  # Would need API call
        return quota

    # Check Mailgun
    mailgun_key = os.getenv("MAILGUN_API_KEY")
    if mailgun_key:
        quota["provider"] = "mailgun"
        quota["daily_limit"] = 300  # Free tier default
        quota["remaining"] = 300
        return quota

    return quota
