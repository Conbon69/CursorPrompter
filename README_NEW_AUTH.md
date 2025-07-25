# 🔐 Custom Email Verification System

This document explains the new lightweight email verification system that replaces Supabase's built-in magic link authentication.

## 📋 **Overview**

The new system provides:
- **Lightweight email verification** without full login/password auth
- **Token-based verification** with 10-minute expiration
- **Simple database schema** with two tables
- **Placeholder email function** ready for Resend/Mailersend integration

## 🗄️ **Database Setup**

### **1. Create Supabase Tables**

Run the SQL in `supabase_tables.sql` in your Supabase SQL Editor:

```sql
-- Table for pending email verifications
CREATE TABLE IF NOT EXISTS pending_verifications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '10 minutes')
);

-- Table for verified users
CREATE TABLE IF NOT EXISTS verified_users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    verified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **2. Required Indexes**

```sql
CREATE INDEX IF NOT EXISTS idx_pending_verifications_token ON pending_verifications(token);
CREATE INDEX IF NOT EXISTS idx_pending_verifications_email ON pending_verifications(email);
CREATE INDEX IF NOT EXISTS idx_pending_verifications_expires_at ON pending_verifications(expires_at);
CREATE INDEX IF NOT EXISTS idx_verified_users_email ON verified_users(email);
```

## 🔄 **Verification Flow**

### **Step 1: User Enters Email**
1. User clicks "🔐 Verify Email" in sidebar
2. Enters email address
3. Clicks "Send Verification Email"
4. System generates UUID token and saves to `pending_verifications`

### **Step 2: Email Sent (Placeholder)**
- Currently displays verification URL in the app
- Ready for integration with Resend, Mailersend, etc.
- URL format: `https://your-app.streamlit.app/?verify_token=abc123`

### **Step 3: User Clicks Link**
1. User clicks verification link in email
2. Gets redirected to app with `?verify_token=abc123`
3. System validates token and expiration
4. If valid, moves user to `verified_users` table
5. Clears URL parameters and shows success message

### **Step 4: Session Management**
- User email stored in `st.session_state["user_email"]`
- Verification status in `st.session_state["is_verified"]`
- Quota increases from 2 to 15 scrapes/day
- Data persists in Supabase database

## 📁 **Files Overview**

| File | Purpose |
|------|---------|
| `email_verification.py` | Core verification logic and functions |
| `streamlit_app_new.py` | New Streamlit app using custom verification |
| `db_helpers.py` | Updated database helpers with new functions |
| `supabase_tables.sql` | SQL for creating required tables |

## 🔧 **Configuration**

### **Environment Variables**
```bash
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
```

### **Streamlit Secrets**
```toml
SUPABASE_URL = "your_supabase_url"
SUPABASE_ANON_KEY = "your_supabase_anon_key"
```

## 🚀 **Running the New System**

### **Local Development**
```bash
streamlit run streamlit_app_new.py
```

### **Streamlit Community Cloud**
1. Upload `streamlit_app_new.py` as your main app
2. Set up secrets in Streamlit dashboard
3. Create Supabase tables using the SQL provided

## 📧 **Email Integration**

### **Current State**
The `send_verification_email()` function is a placeholder that displays the verification URL in the app.

### **Integration Options**

#### **Resend**
```python
import resend

def send_verification_email(email: str, token: str, app_url: str) -> bool:
    verification_url = f"{app_url}?verify_token={token}"
    
    resend.emails.send({
        "from": "noreply@yourdomain.com",
        "to": email,
        "subject": "Verify your email",
        "html": f"<p>Click <a href='{verification_url}'>here</a> to verify your email.</p>"
    })
    return True
```

#### **Mailersend**
```python
import requests

def send_verification_email(email: str, token: str, app_url: str) -> bool:
    verification_url = f"{app_url}?verify_token={token}"
    
    headers = {
        "Authorization": f"Bearer {MAILERSEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "from": {"email": "noreply@yourdomain.com"},
        "to": [{"email": email}],
        "subject": "Verify your email",
        "html": f"<p>Click <a href='{verification_url}'>here</a> to verify your email.</p>"
    }
    
    response = requests.post("https://api.mailersend.com/v1/email", headers=headers, json=data)
    return response.status_code == 202
```

## 🔒 **Security Features**

- **10-minute token expiration** - Tokens automatically expire
- **UUID tokens** - Cryptographically secure random tokens
- **Automatic cleanup** - Expired tokens are removed
- **Email uniqueness** - Each email can only be verified once
- **Session isolation** - Users only see their own data

## 📊 **Quota System**

- **Anonymous users**: 2 scrapes/day
- **Verified users**: 15 scrapes/day
- **Daily reset**: Quota resets at midnight UTC
- **Session persistence**: Quota tracked across page refreshes

## 🔄 **Migration from Old System**

The old authentication system is preserved in:
- `auth_manual.py` (original Supabase auth)
- `streamlit_app.py` (original app)
- Legacy functions in `db_helpers.py`

To switch to the new system:
1. Create the new Supabase tables
2. Deploy `streamlit_app_new.py` instead of `streamlit_app.py`
3. Integrate your preferred email service
4. Test the verification flow

## 🧪 **Testing**

### **Test the Verification Flow**
1. Start the new app: `streamlit run streamlit_app_new.py`
2. Click "🔐 Verify Email"
3. Enter your email
4. Copy the verification URL from the app
5. Paste it in a new browser tab
6. Verify you're logged in and have 15 scrapes

### **Test Data Persistence**
1. Verify your email
2. Run a scrape
3. Refresh the page
4. Verify your data is still there and quota is correct

## 🐛 **Troubleshooting**

### **Common Issues**

1. **"Supabase not configured"**
   - Check your environment variables or Streamlit secrets
   - Verify Supabase URL and API key

2. **"Failed to create verification record"**
   - Check if Supabase tables exist
   - Verify database permissions

3. **"Invalid or expired verification token"**
   - Tokens expire after 10 minutes
   - Request a new verification email

4. **"No previous results found"**
   - Check if user is properly verified
   - Verify database connection

### **Debug Mode**
Add debug logging to `email_verification.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 **Next Steps**

1. **Integrate email service** (Resend, Mailersend, etc.)
2. **Add email templates** with branding
3. **Implement rate limiting** for verification requests
4. **Add email validation** and spam protection
5. **Consider adding** user profiles and preferences 