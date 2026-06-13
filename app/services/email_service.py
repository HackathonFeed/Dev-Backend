"""
Async email service for HackathonFeed.
Uses Gmail SMTP with an App Password — no extra dependencies required.
All sending is done in a thread so it never blocks the async event loop.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from app.core.config import get_settings
from app.core.constants import PLAN_POINTS, SubscriptionPlan
from app.schemas.subscription_schema import PLAN_CATALOGUE


# ── Low-level send ────────────────────────────────────────────────────────────

def _send_sync(to_email: str, subject: str, html_body: str) -> None:
    """Blocking send — must be called inside asyncio.to_thread."""
    settings = get_settings()
    smtp_email = (settings.smtp_email or "").strip()
    smtp_password = (settings.smtp_password or "").strip().replace(" ", "")
    if not smtp_email or not smtp_password:
        logger.warning("SMTP not configured — skipping email to {}", to_email)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{smtp_email}>"
    msg["To"] = to_email
    msg["Reply-To"] = smtp_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
        smtp.login(smtp_email, smtp_password)
        smtp.sendmail(smtp_email, [to_email], msg.as_string())

    logger.info("Email sent → {} | {}", to_email, subject)


async def _send_async(to_email: str, subject: str, html_body: str) -> None:
    """Fire-and-forget async wrapper.  Errors are logged, not raised."""
    try:
        await asyncio.to_thread(_send_sync, to_email, subject, html_body)
    except Exception as exc:  # noqa: BLE001
        logger.error("Email send failed → {} | {}: {}", to_email, subject, exc)


# ── Public API ────────────────────────────────────────────────────────────────

class EmailService:
    @staticmethod
    async def send_welcome(to_email: str, name: str) -> None:
        html = _build_welcome_email(name)
        subject = f"Welcome to HackathonFeed, {name.split()[0]}! 🚀"
        await _send_async(to_email, subject, html)

    @staticmethod
    def send_welcome_bg(to_email: str, name: str) -> None:
        """Schedule a welcome email. Prefer await send_welcome() in async routes."""
        _schedule_email(EmailService.send_welcome(to_email, name))

    @staticmethod
    async def send_reset_code(to_email: str, name: str, code: str) -> None:
        html = _build_reset_code_email(name, code)
        subject = f"Your HackathonFeed reset code: {code}"
        await _send_async(to_email, subject, html)

    @staticmethod
    def send_reset_code_bg(to_email: str, name: str, code: str) -> None:
        """Schedule a password-reset OTP email. Prefer await send_reset_code() in async routes."""
        _schedule_email(EmailService.send_reset_code(to_email, name, code))

    @staticmethod
    async def send_plan_upgrade(
        to_email: str,
        name: str,
        plan: SubscriptionPlan,
        expires_at_str: str | None,
    ) -> None:
        html = _build_upgrade_email(name, plan, expires_at_str)
        plan_info = next((p for p in PLAN_CATALOGUE if p.key == plan), None)
        plan_label = plan_info.name if plan_info else plan.title()
        subject = f"You're now on the {plan_label} plan ⚡"
        await _send_async(to_email, subject, html)

    @staticmethod
    def send_plan_upgrade_bg(
        to_email: str,
        name: str,
        plan: SubscriptionPlan,
        expires_at_str: str | None,
    ) -> None:
        """Schedule a plan-upgrade email. Prefer await send_plan_upgrade() in async routes."""
        _schedule_email(
            EmailService.send_plan_upgrade(to_email, name, plan, expires_at_str),
        )


def _schedule_email(coro) -> None:
    """
    Best-effort background scheduling for sync call sites.
    On serverless (Vercel), pending tasks may be dropped — async routes should await instead.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        logger.warning("No running event loop — email was not scheduled")


# ── HTML template helpers ─────────────────────────────────────────────────────

def _email_wrap(title: str, body_inner: str) -> str:
    """Wrap body content in the shared email shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#e8e3d8;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#e8e3d8;padding:32px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" border="0"
           style="max-width:600px;width:100%;border:4px solid #1a1a1a;
                  box-shadow:8px 8px 0 #1a1a1a;">

      <!-- ── TOP NAV BAR ── -->
      <tr>
        <td style="background:#1a1a1a;padding:16px 28px;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td>
                <span style="font-family:'Arial Black',Arial,sans-serif;
                             font-weight:900;font-size:18px;
                             color:#ffcc00;letter-spacing:-0.5px;
                             text-transform:uppercase;">
                  &#9632; HackathonFeed
                </span>
              </td>
              <td align="right">
                <span style="font-family:'Courier New',monospace;
                             font-size:9px;color:rgba(255,255,255,0.4);
                             text-transform:uppercase;letter-spacing:2px;">
                  THE DEVELOPERS COMMAND CENTER
                </span>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      {body_inner}

      <!-- ── FOOTER ── -->
      <tr>
        <td style="background:#1a1a1a;padding:20px 28px;border-top:4px solid #1a1a1a;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td>
                <p style="font-family:'Courier New',monospace;font-size:9px;
                          color:#888888;text-transform:uppercase;
                          letter-spacing:1.5px;margin:0;">
                  &copy; 2026 HackathonFeed &nbsp;&bull;&nbsp;
                  The Developers Command Center
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


# ── Welcome Email ─────────────────────────────────────────────────────────────

def _build_welcome_email(name: str) -> str:
    first = name.split()[0].upper()
    body = f"""
      <!-- ── HERO ── -->
      <tr>
        <td style="background:#ffcc00;padding:44px 28px 40px;
                   border-bottom:4px solid #1a1a1a;">
          <p style="font-family:'Courier New',monospace;font-size:10px;
                    font-weight:700;text-transform:uppercase;
                    letter-spacing:3px;color:rgba(0,0,0,0.5);margin:0 0 10px;">
            NEW RECRUIT DETECTED
          </p>
          <h1 style="font-family:'Arial Black',Arial,sans-serif;font-weight:900;
                     font-size:48px;text-transform:uppercase;letter-spacing:-2px;
                     color:#1a1a1a;margin:0;line-height:1;">
            WELCOME,<br/>{first}!
          </h1>
          <p style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                    color:#1a1a1a;margin:14px 0 0;line-height:1.5;
                    border-left:4px solid #1a1a1a;padding-left:12px;">
            Your developer command center is live and ready.
          </p>
        </td>
      </tr>

      <!-- ── INTRO TEXT ── -->
      <tr>
        <td style="background:#f5f0e8;padding:32px 28px 20px;
                   border-bottom:2px solid rgba(0,0,0,0.08);">
          <p style="font-family:Arial,sans-serif;font-size:14px;color:#444;
                    line-height:1.7;margin:0;">
            You've just joined the platform built for developers who don't just
            <em>attend</em> hackathons — they <strong>dominate</strong> them.
            From local college fests to global championship stages,
            every hackathon is now in one feed.
          </p>
        </td>
      </tr>

      <!-- ── 3 FEATURE TILES ── -->
      <tr>
        <td style="background:#f5f0e8;padding:20px 28px 28px;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <!-- Aggregate -->
              <td width="31%" valign="top"
                  style="background:#fff;border:3px solid #1a1a1a;
                         padding:18px 14px;
                         box-shadow:4px 4px 0 #1a1a1a;">
                <p style="font-size:24px;margin:0 0 8px;">&#127942;</p>
                <p style="font-family:'Arial Black',Arial,sans-serif;
                          font-weight:900;font-size:12px;
                          text-transform:uppercase;color:#1a1a1a;
                          margin:0 0 4px;letter-spacing:-0.3px;">
                  Aggregate
                </p>
                <p style="font-family:Arial,sans-serif;font-size:11px;
                          color:#666;margin:0;line-height:1.5;">
                  1000+ hackathons across every platform, live.
                </p>
              </td>
              <td width="4%"></td>
              <!-- Track -->
              <td width="31%" valign="top"
                  style="background:#0055ff;border:3px solid #1a1a1a;
                         padding:18px 14px;
                         box-shadow:4px 4px 0 #1a1a1a;">
                <p style="font-size:24px;margin:0 0 8px;">&#9989;</p>
                <p style="font-family:'Arial Black',Arial,sans-serif;
                          font-weight:900;font-size:12px;
                          text-transform:uppercase;color:#ffffff;
                          margin:0 0 4px;letter-spacing:-0.3px;">
                  Track
                </p>
                <p style="font-family:Arial,sans-serif;font-size:11px;
                          color:#c8d8ff;margin:0;line-height:1.5;">
                  Kanban tracker for every app &amp; milestone.
                </p>
              </td>
              <td width="4%"></td>
              <!-- AI Copilot -->
              <td width="31%" valign="top"
                  style="background:#1a1a1a;border:3px solid #1a1a1a;
                         padding:18px 14px;
                         box-shadow:4px 4px 0 #ffcc00;">
                <p style="font-size:24px;margin:0 0 8px;">&#129302;</p>
                <p style="font-family:'Arial Black',Arial,sans-serif;
                          font-weight:900;font-size:12px;
                          text-transform:uppercase;color:#ffcc00;
                          margin:0 0 4px;letter-spacing:-0.3px;">
                  AI Copilot
                </p>
                <p style="font-family:Arial,sans-serif;font-size:11px;
                          color:#cccccc;margin:0;line-height:1.5;">
                  Strategy, ideas &amp; validation — on demand.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── FREE POINTS CHIP ── -->
      <tr>
        <td style="background:#f5f0e8;padding:0 28px 28px;">
          <table cellpadding="0" cellspacing="0" border="0"
                 style="background:#ffcc00;border:3px solid #1a1a1a;
                        box-shadow:4px 4px 0 #1a1a1a;">
            <tr>
              <td style="padding:14px 20px;">
                <table cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="padding-right:14px;">
                      <span style="font-size:28px;">&#9889;</span>
                    </td>
                    <td>
                      <p style="font-family:'Courier New',monospace;
                                font-size:9px;font-weight:700;
                                text-transform:uppercase;letter-spacing:2px;
                                color:rgba(0,0,0,0.5);margin:0 0 2px;">
                        YOUR STARTING BALANCE
                      </p>
                      <p style="font-family:'Arial Black',Arial,sans-serif;
                                font-weight:900;font-size:22px;
                                text-transform:uppercase;color:#1a1a1a;
                                margin:0;letter-spacing:-0.5px;">
                        50 FREE AI POINTS
                      </p>
                      <p style="font-family:Arial,sans-serif;font-size:11px;
                                color:rgba(0,0,0,0.55);margin:4px 0 0;">
                        Each AI chat message costs 5 points &nbsp;&bull;&nbsp;
                        Upgrade anytime for more.
                      </p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── CTA BUTTON ── -->
      <tr>
        <td style="background:#f5f0e8;padding:0 28px 36px;">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="background:#1a1a1a;border:3px solid #1a1a1a;
                         box-shadow:5px 5px 0 #ffcc00;">
                <a href="https://www.hackathonfeed.com/dashboard"
                   style="display:block;padding:16px 36px;
                          font-family:'Arial Black',Arial,sans-serif;
                          font-weight:900;font-size:13px;
                          text-transform:uppercase;letter-spacing:0.5px;
                          color:#ffcc00;text-decoration:none;">
                  EXPLORE HACKATHONS &nbsp;&#8250;
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── DIVIDER ── -->
      <tr>
        <td style="background:#f5f0e8;padding:0 28px 28px;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="border-top:3px solid #1a1a1a;padding-top:20px;">
                <p style="font-family:Arial,sans-serif;font-size:12px;
                          color:#888;margin:0;line-height:1.6;">
                  Need help getting started?
                  Reply to this email — we read everything.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    """
    return _email_wrap(f"Welcome to HackathonFeed — {name}", body)


# ── Plan Upgrade Email ────────────────────────────────────────────────────────

_PLAN_COLORS: dict[SubscriptionPlan, dict[str, str]] = {
    SubscriptionPlan.BUILDER: {
        "bg": "#0055ff",
        "text": "#ffffff",
        "subtext": "#c8d8ff",        # light blue — readable on blue bg
        "badge_bg": "#ffcc00",
        "badge_text": "#1a1a1a",
        "badge_label": "#555555",    # dark label on yellow chip
        "badge_sub": "#555555",      # dark sub-label on yellow chip
        "check": "#0055ff",          # blue check on white features card
    },
    SubscriptionPlan.CHAMPION: {
        "bg": "#1a1a1a",
        "text": "#ffffff",
        "subtext": "#cccccc",        # light grey — readable on dark bg
        "badge_bg": "#e63b2e",
        "badge_text": "#ffffff",
        "badge_label": "#ffc8c2",    # pale pink label — readable on red chip
        "badge_sub": "#ffc8c2",      # pale pink sub-label on red chip
        "check": "#e63b2e",          # red check on white features card
    },
}

_PLAN_EMOJI: dict[SubscriptionPlan, str] = {
    SubscriptionPlan.BUILDER: "&#128640;",   # 🚀
    SubscriptionPlan.CHAMPION: "&#128081;",  # 👑
}


def _build_upgrade_email(
    name: str,
    plan: SubscriptionPlan,
    expires_at_str: str | None,
) -> str:
    first = name.split()[0].upper()
    plan_info = next((p for p in PLAN_CATALOGUE if p.key == plan), None)
    plan_name = plan_info.name if plan_info else plan.title()
    points = PLAN_POINTS[plan]
    points_display = "UNLIMITED" if points == -1 else f"{points:,} PTS"
    features = plan_info.features if plan_info else []

    colors = _PLAN_COLORS.get(plan, _PLAN_COLORS[SubscriptionPlan.BUILDER])
    emoji = _PLAN_EMOJI.get(plan, "&#9889;")

    expiry_row = ""
    if expires_at_str:
        expiry_row = f"""
        <tr>
          <td style="background:#f5f0e8;padding:0 28px 20px;">
            <p style="font-family:'Courier New',monospace;font-size:10px;
                      font-weight:700;text-transform:uppercase;
                      letter-spacing:1.5px;color:#888;margin:0;">
              Plan active until &nbsp;&#8250;&nbsp;
              <span style="color:#1a1a1a;">{expires_at_str}</span>
            </p>
          </td>
        </tr>"""

    feature_rows = "".join(
        f"""<tr>
              <td width="20" valign="top"
                  style="font-family:'Courier New',monospace;font-size:13px;
                         font-weight:700;color:{colors['check']};
                         padding-top:2px;">
                &#10003;
              </td>
              <td style="font-family:Arial,sans-serif;font-size:12px;
                         color:#444;padding-bottom:8px;line-height:1.5;
                         font-weight:600;text-transform:uppercase;">
                {feat}
              </td>
            </tr>"""
        for feat in features
    )

    body = f"""
      <!-- ── HERO ── -->
      <tr>
        <td style="background:{colors['bg']};padding:44px 28px 40px;
                   border-bottom:4px solid #1a1a1a;">
          <p style="font-family:'Courier New',monospace;font-size:10px;
                    font-weight:700;text-transform:uppercase;
                    letter-spacing:3px;color:{colors['subtext']};
                    margin:0 0 10px;">
            PLAN UPGRADE CONFIRMED
          </p>
          <h1 style="font-family:'Arial Black',Arial,sans-serif;font-weight:900;
                     font-size:48px;text-transform:uppercase;letter-spacing:-2px;
                     color:{colors['text']};margin:0;line-height:1;">
            {emoji}&nbsp;{plan_name.upper()}
          </h1>
          <p style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                    color:{colors['text']};margin:14px 0 0;line-height:1.5;
                    border-left:4px solid {colors['badge_bg']};padding-left:12px;">
            Congrats, {first}! Your upgrade is live right now.
          </p>
        </td>
      </tr>

      <!-- ── POINTS CHIP ── -->
      <tr>
        <td style="background:#f5f0e8;padding:28px 28px 20px;
                   border-bottom:2px solid rgba(0,0,0,0.08);">
          <table cellpadding="0" cellspacing="0" border="0"
                 style="background:{colors['badge_bg']};border:3px solid #1a1a1a;
                        box-shadow:4px 4px 0 #1a1a1a;">
            <tr>
              <td style="padding:14px 24px;">
                <p style="font-family:'Courier New',monospace;font-size:9px;
                          font-weight:700;text-transform:uppercase;
                          letter-spacing:2px;color:{colors['badge_label']};
                          margin:0 0 3px;">
                  YOUR NEW BALANCE
                </p>
                <p style="font-family:'Arial Black',Arial,sans-serif;
                          font-weight:900;font-size:26px;
                          text-transform:uppercase;
                          color:{colors['badge_text']};
                          margin:0;letter-spacing:-0.5px;">
                  &#9889; {points_display}
                </p>
                <p style="font-family:Arial,sans-serif;font-size:11px;
                          color:{colors['badge_sub']};margin:4px 0 0;">
                  {plan_info.messages_per_cycle if plan_info else ''}
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── FEATURES ── -->
      <tr>
        <td style="background:#f5f0e8;padding:24px 28px 20px;">
          <p style="font-family:'Arial Black',Arial,sans-serif;font-weight:900;
                    font-size:13px;text-transform:uppercase;color:#1a1a1a;
                    margin:0 0 14px;letter-spacing:-0.3px;">
            WHAT&apos;S INCLUDED IN YOUR PLAN
          </p>
          <table cellpadding="0" cellspacing="0" border="0"
                 style="background:#fff;border:3px solid #1a1a1a;
                        padding:16px 20px;width:100%;
                        box-shadow:4px 4px 0 #1a1a1a;">
            <tr><td>
              <table cellpadding="0" cellspacing="0" border="0" width="100%">
                {feature_rows}
              </table>
            </td></tr>
          </table>
        </td>
      </tr>

      {expiry_row}

      <!-- ── CTA ── -->
      <tr>
        <td style="background:#f5f0e8;padding:8px 28px 36px;">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="background:{colors['bg']};border:3px solid #1a1a1a;
                         box-shadow:5px 5px 0 #ffcc00;">
                <a href="https://www.hackathonfeed.com/dashboard"
                   style="display:block;padding:16px 36px;
                          font-family:'Arial Black',Arial,sans-serif;
                          font-weight:900;font-size:13px;
                          text-transform:uppercase;letter-spacing:0.5px;
                          color:{colors['text']};text-decoration:none;">
                  OPEN AI COPILOT &nbsp;&#8250;
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── NOTICE ── -->
      <tr>
        <td style="background:#f5f0e8;padding:0 28px 28px;">
          <p style="font-family:Arial,sans-serif;font-size:11px;
                    color:#666666;margin:0;line-height:1.6;
                    border-top:2px solid rgba(0,0,0,0.12);padding-top:16px;">
            This email confirms your plan upgrade. If you did not make this
            purchase, reply immediately and we&apos;ll look into it.
          </p>
        </td>
      </tr>
    """
    return _email_wrap(f"{plan_name} Plan Confirmed — HackathonFeed", body)


# ── Password Reset OTP Email ──────────────────────────────────────────────────

def _build_reset_code_email(name: str, code: str) -> str:
    first = name.split()[0].upper() if name else "HACKER"
    # Split code into individual digit spans for the big display
    digit_cells = "".join(
        f"""<td style="width:48px;height:60px;background:#fff;
                      border:3px solid #1a1a1a;
                      text-align:center;vertical-align:middle;
                      font-family:'Arial Black',Arial,sans-serif;
                      font-weight:900;font-size:30px;color:#1a1a1a;
                      letter-spacing:-1px;padding:0 4px;">
              {d}
            </td>
            <td width="6"></td>"""
        for d in code
    )
    body = f"""
      <!-- ── HERO ── -->
      <tr>
        <td style="background:#e63b2e;padding:44px 28px 40px;
                   border-bottom:4px solid #1a1a1a;">
          <p style="font-family:'Courier New',monospace;font-size:10px;
                    font-weight:700;text-transform:uppercase;
                    letter-spacing:3px;color:rgba(255,255,255,0.7);
                    margin:0 0 10px;">
            SECURITY VERIFICATION
          </p>
          <h1 style="font-family:'Arial Black',Arial,sans-serif;font-weight:900;
                     font-size:42px;text-transform:uppercase;letter-spacing:-2px;
                     color:#fff;margin:0;line-height:1;">
            RESET CODE,<br/>{first}
          </h1>
          <p style="font-family:Arial,sans-serif;font-size:14px;font-weight:700;
                    color:rgba(255,255,255,0.85);margin:14px 0 0;line-height:1.5;
                    border-left:4px solid #ffcc00;padding-left:12px;">
            Use this one-time code to reset your password.
            It expires in <strong style="color:#ffcc00;">15 minutes</strong>.
          </p>
        </td>
      </tr>

      <!-- ── OTP CODE BOX ── -->
      <tr>
        <td style="background:#f5f0e8;padding:36px 28px 28px;">
          <p style="font-family:'Courier New',monospace;font-size:9px;
                    font-weight:700;text-transform:uppercase;letter-spacing:2.5px;
                    color:rgba(0,0,0,0.4);margin:0 0 16px;">
            YOUR ONE-TIME CODE
          </p>
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              {digit_cells}
            </tr>
          </table>
          <p style="font-family:'Courier New',monospace;font-size:9px;
                    font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
                    color:rgba(0,0,0,0.4);margin:16px 0 0;">
            &#9200; Expires in 15 minutes
          </p>
        </td>
      </tr>

      <!-- ── INSTRUCTIONS ── -->
      <tr>
        <td style="background:#f5f0e8;padding:4px 28px 28px;">
          <table cellpadding="0" cellspacing="0" border="0" width="100%"
                 style="background:#fff;border:3px solid #1a1a1a;
                        padding:18px 20px;box-shadow:4px 4px 0 #1a1a1a;">
            <tr>
              <td>
                <p style="font-family:'Arial Black',Arial,sans-serif;font-weight:900;
                          font-size:12px;text-transform:uppercase;color:#1a1a1a;
                          margin:0 0 10px;">HOW TO USE THIS CODE</p>
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td width="20" valign="top"
                        style="font-family:'Courier New',monospace;font-size:13px;
                               font-weight:700;color:#e63b2e;padding-top:2px;">
                      1.
                    </td>
                    <td style="font-family:Arial,sans-serif;font-size:12px;
                               color:#444;padding-bottom:6px;line-height:1.5;font-weight:600;">
                      Go back to the HackathonFeed login page.
                    </td>
                  </tr>
                  <tr>
                    <td width="20" valign="top"
                        style="font-family:'Courier New',monospace;font-size:13px;
                               font-weight:700;color:#e63b2e;padding-top:2px;">
                      2.
                    </td>
                    <td style="font-family:Arial,sans-serif;font-size:12px;
                               color:#444;padding-bottom:6px;line-height:1.5;font-weight:600;">
                      Enter the 6-digit code shown above.
                    </td>
                  </tr>
                  <tr>
                    <td width="20" valign="top"
                        style="font-family:'Courier New',monospace;font-size:13px;
                               font-weight:700;color:#e63b2e;padding-top:2px;">
                      3.
                    </td>
                    <td style="font-family:Arial,sans-serif;font-size:12px;
                               color:#444;padding-bottom:6px;line-height:1.5;font-weight:600;">
                      Set your new password. Done!
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── SECURITY NOTICE ── -->
      <tr>
        <td style="background:#f5f0e8;padding:0 28px 36px;">
          <p style="font-family:Arial,sans-serif;font-size:11px;
                    color:#666666;margin:0;line-height:1.6;
                    border-top:2px solid rgba(0,0,0,0.12);padding-top:16px;">
            If you did not request a password reset, ignore this email —
            your account remains secure. Never share this code with anyone.
          </p>
        </td>
      </tr>
    """
    return _email_wrap("Password Reset Code — HackathonFeed", body)
