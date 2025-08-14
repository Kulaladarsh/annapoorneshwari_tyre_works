#!/usr/bin/env python3
"""
Email Configuration Diagnostic Script
Run this script to diagnose email sending issues
"""

import os
from dotenv import load_dotenv

def check_email_config():
    """Check if email configuration is properly set"""
    print("🔧 Email Configuration Diagnostic")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Check required email environment variables
    email_user = os.environ.get("EMAIL_USER")
    email_pass = os.environ.get("EMAIL_PASS")
    
    print("📧 Checking email configuration...")
    
    if not email_user:
        print("❌ EMAIL_USER environment variable is not set")
        print("Please add to your .env file:")
        print("EMAIL_USER=your-email@gmail.com")
    else:
        print(f"✅ EMAIL_USER: {email_user}")
    
    if not email_pass:
        print("❌ EMAIL_PASS environment variable is not set")
        print("Please add to your .env file:")
        print("EMAIL_PASS=your-app-password")
    else:
        print(f"✅ EMAIL_PASS: {'*' * len(email_pass) if email_pass else 'Not set'}")
    
    if email_user and email_pass:
        print("\n✅ Email configuration is complete")
        print("You can now test email sending functionality")
    else:
        print("\n❌ Email configuration is incomplete")
        print("Please set the missing environment variables")

def create_email_env_template():
    """Create email configuration template"""
    template = """
# Email Configuration for Gmail SMTP
# Replace with your actual email credentials
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password

# To get app password for Gmail:
# 1. Go to https://myaccount.google.com/security
# 2. Enable 2-factor authentication
# 3. Generate app password for "Mail"
# 4. Use the 16-character app password as EMAIL_PASS
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'a') as f:
            f.write(template)
        print("✅ Added email configuration template to .env")
    else:
        with open('.env', 'r') as f:
            content = f.read()
            if 'EMAIL_USER' not in content or 'EMAIL_PASS' not in content:
                with open('.env', 'a') as f:
                    f.write(template)
                print("✅ Added email configuration template to .env")
            else:
                print("ℹ️  Email configuration already exists in .env")

if __name__ == "__main__":
    check_email_config()
    create_email_env_template()
