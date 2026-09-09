import resend
from app.config import RESEND_API_KEY, FROM_EMAIL

resend.api_key = RESEND_API_KEY


def send_welcome_email(to_email: str):
    """Fire-and-forget welcome email on signup. Failure here should never
    block account creation — caught and logged, not raised."""
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": "Welcome to DocQuery",
            "html": """
                <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                    <h2 style="color: #201C16;">Welcome to DocQuery</h2>
                    <p>Your account is ready. Upload a PDF and start asking it questions — every answer comes with the exact page it was drawn from.</p>
                </div>
            """,
        })
    except Exception as e:
        # Signup should succeed even if the email provider is down/misconfigured.
        print(f"[email] Failed to send welcome email to {to_email}: {e}")