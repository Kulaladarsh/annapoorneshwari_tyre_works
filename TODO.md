# OTP Email Configuration Fix

## Current Status
- ✅ Identified issue: Gmail app password authentication failed
- ✅ Test script confirmed email sending fails with auth error
- 🔄 Need to regenerate Gmail app password (previous one expired/invalid)

## Tasks to Complete
- [x] Regenerate Gmail app password (previous one expired)
- [x] Update EMAIL_PASS in .env file with new app password
- [x] Test OTP sending functionality
- [ ] Verify login OTP works
- [ ] Verify forgot password OTP works
- [ ] Test prebooking OTP functionality

## Gmail App Password Regeneration
1. Go to https://myaccount.google.com/security
2. Click "App passwords" under "Signing in to Google"
3. Revoke the old "Mail" app password if it exists
4. Generate a new app password for "Mail" → "Windows Computer"
5. Update .env file with the new 16-character password
6. Restart Flask application
7. Test OTP functionality

## Testing Checklist
- [ ] Login OTP sends successfully
- [ ] Forgot password OTP sends successfully
- [ ] Prebooking OTP sends successfully
- [ ] Emails are received (check spam folder)
- [ ] OTP verification works correctly
