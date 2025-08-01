# Resend Email Setup Guide

## Step 1: Get Your Resend API Key

1. **Sign up at [resend.com](https://resend.com)**
   - Go to https://resend.com
   - Click "Get Started" or "Sign Up"
   - Create your account

2. **Get your API key**
   - After signing up, go to your dashboard
   - Look for "API Keys" in the sidebar
   - Click "Create API Key"
   - Give it a name like "Reddit SaaS Finder"
   - Copy the API key (starts with `re_`)

## Step 2: Set Environment Variable

### Option A: Windows PowerShell
```powershell
$env:RESEND_API_KEY="re_your_actual_api_key_here"
```

### Option B: Windows Command Prompt
```cmd
set RESEND_API_KEY=re_your_actual_api_key_here
```

### Option C: Create a .env file
Create a file called `.env` in your project root:
```
RESEND_API_KEY=re_your_actual_api_key_here
```

## Step 3: Test the Setup

1. **Restart your FastAPI app**
   ```bash
   python main_fastapi.py
   ```

2. **Try the verification flow**
   - Go to http://localhost:8000/verify
   - Enter your email address
   - Click "Send Verification Email"
   - Check your email inbox

## Step 4: Verify It's Working

You should see:
- ✅ "Email sent successfully" in the console
- A beautiful HTML email in your inbox
- Click the verification link to complete the process

## Troubleshooting

### "RESEND_API_KEY environment variable not set"
- Make sure you set the environment variable correctly
- Restart your terminal/command prompt after setting it
- Or restart your FastAPI app

### "Resend not installed"
- Run: `pip install resend`

### Email not received
- Check your spam folder
- Verify the API key is correct
- Check the Resend dashboard for delivery status

## Production Setup

For production on `launchctrl.ai`:

1. **Verify your domain** in Resend dashboard
2. **Update the from email** in `email_verification.py`:
   ```python
   from_email = "noreply@launchctrl.ai"  # Your verified domain
   ```
3. **Set environment variable** on your production server

## Current Status

✅ **Resend package installed**  
✅ **Email function updated**  
✅ **FastAPI integration ready**  
⏳ **Waiting for your API key**  

Once you set the `RESEND_API_KEY` environment variable, real email sending will work! 