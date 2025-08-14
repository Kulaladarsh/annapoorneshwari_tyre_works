# Gmail SMTP Setup Guide

## Issue Identified
The error `(535, b'5.7.8 Username and Password not accepted')` indicates that Gmail is rejecting the login credentials. This is because Gmail requires app-specific passwords for SMTP access.

## Solution Steps

### 1. Enable 2-Factor Authentication
1. Go to https://myaccount.google.com/security
2. Sign in with your Gmail account
3. Under "Signing in to Google", click "2-Step Verification"
4. Follow the prompts to enable 2FA

### 2. Generate App Password
1. After enabling 2FA, go back to https://myaccount.google.com/security
2. Under "Signing in to Google", click "App passwords"
3. Click "Select app" → "Mail"
4. Click "Select device" → "Windows Computer"
5. Click "Generate"
6. Copy the 16-character app password (it looks like: abcd-efgh-ijkl-mnop)

### 3. Update Environment Variables
Add these to your `.env` file:
```
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-16-character-app-password
```

### 4. Test Email Functionality
After setting up, test the email functionality:
- Visit http://127.0.0.1:5000
- Try to prebook a service
- Check if OTP email is sent successfully

## Alternative Solutions

### Option 1: Use Gmail App Password (Recommended)
- Most secure method
- Works with Gmail accounts
- Follow steps above

### Option 2: Use Other Email Providers
If Gmail doesn't work, you can use other providers:

**For Outlook/Hotmail:**
```
EMAIL_USER=your-email@outlook.com
EMAIL_PASS=your-password
```

**For Yahoo:**
```
EMAIL_USER=your-email@yahoo.com
EMAIL_PASS=your-password
```

### Option 3: Use Environment-Specific Settings
For development, you can use a test email service:

**For testing (Mailtrap):**
1. Sign up at https://mailtrap.io
2. Get SMTP credentials
3. Update app.py to use Mailtrap settings

## Verification Steps
1. Run `python email_diagnostic.py` to check configuration
2. Ensure .env file has correct credentials
3. Test OTP functionality on the website
4. Check spam folder for test emails

## Security Notes
- Never commit .env file to version control
- Use app passwords instead of regular passwords
- Rotate app passwords regularly
- Monitor email sending limits
