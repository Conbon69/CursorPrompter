"""
FastAPI Email Verification System
Standalone email verification without Streamlit dependencies
"""

import uuid
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
from supabase import create_client

# Get Supabase client
SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_ANON_KEY")

if SB_URL and SB_KEY:
    sb = create_client(SB_URL, SB_KEY)
else:
    sb = None

def generate_verification_token() -> str:
    """Generate a secure random token for email verification"""
    return str(uuid.uuid4())

def create_verification_record(email: str) -> Optional[str]:
    """Create a verification record in Supabase and return the token"""
    if not sb:
        print("❌ Supabase not configured")
        return None
    
    try:
        print(f"🔍 Creating verification record for {email}")
        
        # Generate token
        token = generate_verification_token()
        print(f"🔑 Generated token: {token[:20]}...")
        
        # Calculate expiration (10 minutes from now)
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        print(f"⏰ Expires at: {expires_at.isoformat()}")
        
        # Prepare data
        data = {
            "email": email,
            "token": token,
            "expires_at": expires_at.isoformat()
        }
        print(f"📝 Data to insert: {data}")
        
        # Insert into pending_verifications table
        print("🚀 Attempting to insert into pending_verifications...")
        response = sb.table("pending_verifications").insert(data).execute()
        
        print(f"📊 Response: {response}")
        
        if response.data:
            print("✅ Verification record created successfully")
            return token
        else:
            print("❌ No data returned from insert")
            return None
            
    except Exception as e:
        print(f"❌ Error creating verification record: {e}")
        print(f"🔍 Full error details: {str(e)}")
        return None

def verify_token(token: str) -> Tuple[bool, Optional[str]]:
    """Verify a token and return (success, email)"""
    if not sb:
        return False, None
    
    try:
        # Check if token exists and is not expired
        response = sb.table("pending_verifications").select("*").eq("token", token).execute()
        
        if not response.data:
            return False, None
        
        verification = response.data[0]
        email = verification["email"]
        
        # Check if expired
        expires_at = datetime.fromisoformat(verification["expires_at"].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
            # Token expired, clean it up
            sb.table("pending_verifications").delete().eq("token", token).execute()
            return False, None
        
        # Token is valid, move user to verified_users table
        try:
            # Insert into verified_users (ignore if already exists)
            verified_data = {
                "email": email,
                "verified_at": datetime.utcnow().isoformat(),
                "last_login": datetime.utcnow().isoformat()
            }
            
            sb.table("verified_users").upsert(verified_data, on_conflict="email").execute()
            
            # Clean up the pending verification
            sb.table("pending_verifications").delete().eq("token", token).execute()
            
            return True, email
            
        except Exception as e:
            print(f"Error moving user to verified_users: {e}")
            return False, None
            
    except Exception as e:
        print(f"Error verifying token: {e}")
        return False, None

def is_email_verified(email: str) -> bool:
    """Check if an email is verified"""
    if not sb:
        return False
    
    try:
        response = sb.table("verified_users").select("email").eq("email", email).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking email verification: {e}")
        return False

def update_last_login(email: str):
    """Update the last_login timestamp for a verified user"""
    if not sb:
        return
    
    try:
        data = {
            "email": email,
            "last_login": datetime.utcnow().isoformat()
        }
        sb.table("verified_users").upsert(data, on_conflict="email").execute()
    except Exception as e:
        print(f"Error updating last login: {e}")

def send_verification_email_fastapi(email: str, token: str, app_url: str) -> bool:
    """Send verification email using Resend (FastAPI version)"""
    try:
        import resend
        
        # Get API key from environment variable
        resend_api_key = os.getenv("RESEND_API_KEY")
        print(f"🔍 Email Debug: RESEND_API_KEY = {resend_api_key[:10] if resend_api_key else 'None'}...")
        if not resend_api_key:
            print("❌ RESEND_API_KEY environment variable not set")
            return False
        
        # Set API key
        resend.api_key = resend_api_key
        
        # Choose sender. Prefer verified domain via env; fallback to sandbox (delivery restrictions apply)
        from_email = os.getenv("RESEND_FROM_EMAIL", "Acme <onboarding@resend.dev>")
        if "onboarding@resend.dev" in from_email:
            print("ℹ️ Using Resend sandbox sender. Delivery may be restricted unless your recipient is allowed by Resend.")
        
        # Generate verification URL for FastAPI
        verification_url = f"{app_url}verify/confirm?token={token}"
        print(f"📧 Sending email to {email} with verification URL: {verification_url}")
        
        # Attempt to send email
        response = resend.Emails.send({
            "from": from_email,
            "to": [email],
            "subject": "Verify your email - LaunchCtrl",
            "html": f"""
            <div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;\">
                <h2 style=\"color: #333;\">🚀 Welcome to LaunchCtrl!</h2>
                <p>Thanks for signing up! Click the button below to verify your email address and unlock 15 scrapes per day:</p>
                
                <div style=\"text-align: center; margin: 30px 0;\">
                    <a href=\"{verification_url}\" style=\"background-color: #007bff; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;\">
                        ✅ Verify Email Address
                    </a>
                </div>
                
                <p style=\"color: #666; font-size: 14px;\">
                    Or copy and paste this link into your browser:<br>
                    <a href=\"{verification_url}\" style=\"color: #007bff;\">{verification_url}</a>
                </p>
                
                <div style=\"background-color: #fff3cd; padding: 15px; border-radius: 6px; margin: 20px 0;\">
                    <p style=\"margin: 0; color: #856404;\">
                        ⚠️ <strong>Important:</strong> This verification link will expire in 10 minutes.
                    </p>
                </div>
                
                <p style=\"color: #666; font-size: 14px;\">
                    If you didn't request this verification, you can safely ignore this email.
                </p>
            </div>
            """
        })
        print(f"📊 Resend response: {response}")
        
        if hasattr(response, 'id') and response.id:
            print(f"✅ Email sent successfully to {email}")
            return True
        else:
            print(f"❌ Failed to send email to {email}")
            return False
            
    except ImportError:
        print("❌ Resend not installed. Run: pip install resend")
        return False
    except Exception as e:
        print(f"❌ Resend error: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        return False 