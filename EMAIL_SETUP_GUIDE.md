# Email Setup Guide for FastAPI App

## Current Status
The email verification system is working, but **email sending is not configured**. Currently, when users request verification, they get a manual verification link instead of an email.

## Quick Fix (Current Workaround)
Users can still verify their email by:
1. Entering their email on the verification page
2. Clicking the manual verification link that appears
3. The verification works perfectly - they get 15 scrapes per day

## Setting Up Real Email Sending

### Option 1: Resend (Recommended)
1. Sign up at [resend.com](https://resend.com)
2. Get your API key
3. Install: `pip install resend`
4. Update `email_verification.py`:

```python
# In email_verification.py, uncomment the Resend section and add your API key:
import resend
resend.api_key = "re_your_api_key_here"  # Replace with your actual key

# Also update the "from" email to your verified domain
"from": "noreply@yourdomain.com",  # Replace with your domain
```

### Option 2: MailerSend
1. Sign up at [mailersend.com](https://mailersend.com)
2. Get your API key
3. Update `email_verification.py`:

```python
# In email_verification.py, uncomment the MailerSend section and add your API key:
MAILERSEND_API_KEY = "your_mailersend_api_key_here"  # Replace with your actual key
```

### Option 3: Gmail SMTP (Simple)
1. Enable 2-factor authentication on your Gmail
2. Generate an app password
3. Add to your environment variables:
```bash
export GMAIL_USER="your@gmail.com"
export GMAIL_PASSWORD="your_app_password"
```

Then uncomment and configure the Gmail section in `email_verification.py`.

## Testing Email Setup
1. Configure one of the email services above
2. Restart your FastAPI app
3. Try the verification flow
4. Check if emails are received

## Production Deployment
For production on `launchctrl.ai`:
1. Use a professional email service (Resend or MailerSend)
2. Set up proper domain verification
3. Configure SPF/DKIM records
4. Monitor email delivery rates

## Current Workflow (No Email Setup Required)
✅ **Verification works without email setup:**
1. User enters email → Gets manual verification link
2. User clicks link → Email is verified
3. User gets 15 scrapes per day
4. Session persists across browser restarts

The system is fully functional even without email sending configured! 