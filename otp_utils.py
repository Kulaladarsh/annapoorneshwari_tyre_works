"""
Enhanced OTP Utility Module
Provides secure OTP generation, validation, rate limiting, and management
"""
import hashlib
import time
import random
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import session, flash, request

logger = logging.getLogger(__name__)

class OTPManager:
    """Enhanced OTP Manager with security features"""

    def __init__(self):
        # Rate limiting settings
        self.max_requests_per_hour = 5
        self.max_attempts_per_session = 3
        self.otp_expiry_seconds = 300  # 5 minutes
        self.resend_cooldown_seconds = 60  # 1 minute between resends

    def generate_otp(self):
        """Generate a secure 6-digit OTP"""
        return str(random.randint(100000, 999999))

    def hash_otp(self, otp):
        """Hash OTP for secure storage in session"""
        return hashlib.sha256(otp.encode()).hexdigest()

    def check_rate_limit(self, email, otp_type):
        """Check if user has exceeded rate limits"""
        key = f"{otp_type}_requests_{email}"
        current_time = time.time()

        # Get existing requests
        requests = session.get(key, [])

        # Filter out old requests (older than 1 hour)
        recent_requests = [req_time for req_time in requests
                          if current_time - req_time < 3600]

        # Check rate limit
        if len(recent_requests) >= self.max_requests_per_hour:
            return False, "Too many OTP requests. Please try again later."

        # Add current request
        recent_requests.append(current_time)
        session[key] = recent_requests

        return True, None

    def check_attempt_limit(self, otp_type):
        """Check if user has exceeded attempt limits"""
        key = f"{otp_type}_attempts"
        attempts = session.get(key, 0)

        if attempts >= self.max_attempts_per_session:
            return False, "Too many failed attempts. Please request a new OTP."

        return True, None

    def increment_attempts(self, otp_type):
        """Increment failed attempt counter"""
        key = f"{otp_type}_attempts"
        attempts = session.get(key, 0) + 1
        session[key] = attempts

    def reset_attempts(self, otp_type):
        """Reset attempt counter on successful verification"""
        key = f"{otp_type}_attempts"
        session.pop(key, None)

    def can_resend_otp(self, otp_type):
        """Check if user can resend OTP (cooldown period)"""
        key = f"{otp_type}_last_sent"
        last_sent = session.get(key)

        if not last_sent:
            return True, None

        time_since_last = time.time() - last_sent
        if time_since_last < self.resend_cooldown_seconds:
            remaining = int(self.resend_cooldown_seconds - time_since_last)
            return False, f"Please wait {remaining} seconds before requesting another OTP."

        return True, None

    def store_otp(self, otp, otp_type, email, user_data=None):
        """Securely store OTP in session with metadata"""
        hashed_otp = self.hash_otp(otp)
        current_time = time.time()

        session[f"{otp_type}_otp"] = hashed_otp
        session[f"{otp_type}_otp_time"] = current_time
        session[f"{otp_type}_email"] = email
        session[f"{otp_type}_last_sent"] = current_time

        # Store additional user data if provided
        if user_data:
            for key, value in user_data.items():
                session[f"{otp_type}_{key}"] = value

        # Reset attempt counter for new OTP
        self.reset_attempts(otp_type)

        logger.info(f"OTP stored for {otp_type} - Email: {email}")

    def verify_otp(self, entered_otp, otp_type):
        """Verify entered OTP with enhanced security"""
        # Check if OTP exists
        stored_hash = session.get(f"{otp_type}_otp")
        if not stored_hash:
            return False, "No OTP found. Please request a new one."

        # Check expiry
        otp_time = session.get(f"{otp_type}_otp_time")
        if not otp_time or time.time() - otp_time > self.otp_expiry_seconds:
            self.clear_otp(otp_type)
            return False, "OTP has expired. Please request a new one."

        # Check attempt limit
        can_attempt, error_msg = self.check_attempt_limit(otp_type)
        if not can_attempt:
            return False, error_msg

        # Verify OTP
        entered_hash = self.hash_otp(entered_otp)
        if entered_hash == stored_hash:
            # Success - clear OTP and reset attempts
            self.clear_otp(otp_type)
            self.reset_attempts(otp_type)
            logger.info(f"OTP verified successfully for {otp_type}")
            return True, None
        else:
            # Failed - increment attempts
            self.increment_attempts(otp_type)
            remaining_attempts = self.max_attempts_per_session - session.get(f"{otp_type}_attempts", 0)
            return False, f"Invalid OTP. {remaining_attempts} attempts remaining."

    def clear_otp(self, otp_type):
        """Clear OTP data from session"""
        keys_to_clear = [
            f"{otp_type}_otp",
            f"{otp_type}_otp_time",
            f"{otp_type}_email",
            f"{otp_type}_last_sent",
            f"{otp_type}_attempts"
        ]

        # Clear user data keys (any key starting with otp_type_)
        all_keys = list(session.keys())
        for key in all_keys:
            if key.startswith(f"{otp_type}_"):
                keys_to_clear.append(key)

        for key in keys_to_clear:
            session.pop(key, None)

        logger.info(f"OTP data cleared for {otp_type}")

    def get_otp_status(self, otp_type):
        """Get current OTP status for debugging/UI"""
        otp_time = session.get(f"{otp_type}_otp_time")
        last_sent = session.get(f"{otp_type}_last_sent")
        attempts = session.get(f"{otp_type}_attempts", 0)

        status = {
            "has_otp": bool(session.get(f"{otp_type}_otp")),
            "attempts_used": attempts,
            "max_attempts": self.max_attempts_per_session,
            "can_resend": False,
            "resend_cooldown": 0
        }

        if otp_time:
            time_elapsed = time.time() - otp_time
            status["time_elapsed"] = int(time_elapsed)
            status["time_remaining"] = max(0, int(self.otp_expiry_seconds - time_elapsed))
            status["is_expired"] = time_elapsed > self.otp_expiry_seconds

        if last_sent:
            time_since_sent = time.time() - last_sent
            if time_since_sent < self.resend_cooldown_seconds:
                status["resend_cooldown"] = int(self.resend_cooldown_seconds - time_since_sent)
            else:
                status["can_resend"] = True

        return status

# Global OTP manager instance
otp_manager = OTPManager()

def create_enhanced_email_template(otp, otp_type, recipient_name=None):
    """Create enhanced HTML email template for OTP"""
    otp_types = {
        "login": "Login",
        "reset": "Password Reset",
        "prebook": "Pre-booking Verification"
    }

    type_title = otp_types.get(otp_type, "Verification")

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{type_title} OTP - Annapoorneshwari Works</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                background-color: #f4f4f4;
                padding: 20px;
            }}
            .container {{
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #007bff;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }}
            .otp-box {{
                background-color: #f8f9fa;
                border: 2px solid #007bff;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                margin: 20px 0;
                font-size: 24px;
                font-weight: bold;
                letter-spacing: 3px;
                color: #007bff;
            }}
            .warning {{
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 5px;
                padding: 15px;
                margin: 20px 0;
                color: #856404;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                text-align: center;
                color: #6c757d;
                font-size: 12px;
            }}
            .security-note {{
                background-color: #e7f3ff;
                border-left: 4px solid #007bff;
                padding: 15px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Annapoorneshwari Tyre & Painting Works</h1>
                <h2>{type_title} Verification</h2>
            </div>

            {"<p>Dear " + recipient_name + ",</p>" if recipient_name else "<p>Hello,</p>"}

            <p>You have requested a One-Time Password (OTP) for {type_title.lower()}. Please use the following code to complete your verification:</p>

            <div class="otp-box">
                {otp}
            </div>

            <div class="warning">
                <strong>⚠️ Important:</strong>
                <ul>
                    <li>This OTP will expire in <strong>5 minutes</strong></li>
                    <li>Do not share this code with anyone</li>
                    <li>This code can only be used once</li>
                </ul>
            </div>

            <div class="security-note">
                <strong>🔒 Security Notice:</strong><br>
                If you did not request this OTP, please ignore this email and contact our support team immediately.
            </div>

            <p>If you have any questions or need assistance, please don't hesitate to contact us.</p>

            <p>Best regards,<br>
            <strong>Annapoorneshwari Tyre & Painting Works Team</strong></p>

            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>For support, contact us at: support@annapoorneshwariworks.com</p>
                <p>&copy; 2024 Annapoorneshwari Tyre & Painting Works. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Plain text fallback
    text_body = f"""
    Annapoorneshwari Tyre & Painting Works

    {type_title} OTP: {otp}

    This OTP will expire in 5 minutes.
    Do not share this code with anyone.

    If you did not request this OTP, please contact support immediately.

    Best regards,
    Annapoorneshwari Works Team
    """

    return html_template, text_body

def cleanup_expired_otps():
    """Clean up expired OTPs from session (can be called periodically)"""
    current_time = time.time()
    otp_types = ['login', 'reset', 'prebook']

    for otp_type in otp_types:
        otp_time = session.get(f"{otp_type}_otp_time")
        if otp_time and current_time - otp_time > 300:  # 5 minutes
            otp_manager.clear_otp(otp_type)
            logger.info(f"Cleaned up expired {otp_type} OTP")

# Decorator for OTP-protected routes
def require_otp_verification(otp_type):
    """Decorator to require OTP verification for routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get(f"{otp_type}_verified", False):
                flash(f"Please complete {otp_type} verification first.", "warning")
                return redirect(url_for(f"{otp_type}_otp"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
