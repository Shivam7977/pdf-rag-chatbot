import resend
from app.config import RESEND_API_KEY, FROM_EMAIL

resend.api_key = RESEND_API_KEY


def send_verification_email(to_email: str, code: str):
    """Not fire-and-forget like the welcome email — if this fails, signup
    should fail too, since the user can never verify without it."""
    resend.Emails.send({
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": "Verify your DocQuery account",
        "html": f"""
            <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                <h2 style="color: #201C16;">Verify your email</h2>
                <p>Your verification code is:</p>
                <p style="font-size: 28px; font-weight: 600; letter-spacing: 4px;">{code}</p>
                <p style="color: #6B6255; font-size: 14px;">This code expires in 15 minutes.</p>
            </div>
        """,
    })


def send_welcome_email(to_email: str):
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
        print(f"[email] Failed to send welcome email to {to_email}: {e}")