"""
Custom Email Verification System
Replaces Supabase magic link auth with lightweight email verification
"""

import uuid
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, Tuple
from supabase import create_client

# Get Supabase client
try:
    SB_URL = st.secrets["SUPABASE_URL"]
    SB_KEY = st.secrets["SUPABASE_ANON_KEY"]
except:
    import os
    SB_URL = os.getenv("SUPABASE_URL")
    SB_KEY = os.getenv("SUPABASE_ANON_KEY")

if SB_URL and SB_KEY:
    sb = create_client(SB_URL, SB_KEY)
else:
    sb = None

def debug_supabase_connection():
    """Debug function to check Supabase connection and tables"""
    if not sb:
        st.error("❌ Supabase client not available")
        st.write("SB_URL:", "✅ Set" if SB_URL else "❌ Missing")
        st.write("SB_KEY:", "✅ Set" if SB_KEY else "❌ Missing")
        return False
    
    try:
        # Test basic connection
        st.success("✅ Supabase client created")
        
        # Test if tables exist
        try:
            # Try to select from pending_verifications table
            response = sb.table("pending_verifications").select("count", count="exact").limit(1).execute()
            st.success("✅ pending_verifications table exists")
        except Exception as e:
            st.error(f"❌ pending_verifications table not found: {e}")
            return False
        
        try:
            # Try to select from verified_users table
            response = sb.table("verified_users").select("count", count="exact").limit(1).execute()
            st.success("✅ verified_users table exists")
        except Exception as e:
            st.error(f"❌ verified_users table not found: {e}")
            return False
        
        return True
        
    except Exception as e:
        st.error(f"❌ Supabase connection error: {e}")
        return False

def generate_verification_token() -> str:
    """Generate a secure random token for email verification"""
    return str(uuid.uuid4())

def create_verification_record(email: str) -> Optional[str]:
    """Create a verification record in Supabase and return the token"""
    if not sb:
        st.error("Supabase not configured")
        return None
    
    try:
        # Debug: Show what we're trying to do
        st.info(f"🔍 Creating verification record for {email}")
        
        # Generate token
        token = generate_verification_token()
        st.info(f"🔑 Generated token: {token[:20]}...")
        
        # Calculate expiration (10 minutes from now)
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        st.info(f"⏰ Expires at: {expires_at.isoformat()}")
        
        # Prepare data
        data = {
            "email": email,
            "token": token,
            "expires_at": expires_at.isoformat()
        }
        st.info(f"📝 Data to insert: {data}")
        
        # Insert into pending_verifications table
        st.info("🚀 Attempting to insert into pending_verifications...")
        response = sb.table("pending_verifications").insert(data).execute()
        
        st.info(f"📊 Response: {response}")
        
        if response.data:
            st.success("✅ Verification record created successfully")
            return token
        else:
            st.error("❌ No data returned from insert")
            return None
            
    except Exception as e:
        st.error(f"❌ Error creating verification record: {e}")
        st.write("🔍 Full error details:", str(e))
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
            st.error(f"Error moving user to verified_users: {e}")
            return False, None
            
    except Exception as e:
        st.error(f"Error verifying token: {e}")
        return False, None

def is_email_verified(email: str) -> bool:
    """Check if an email is verified"""
    if not sb:
        return False
    
    try:
        response = sb.table("verified_users").select("email").eq("email", email).execute()
        return len(response.data) > 0
    except Exception as e:
        st.error(f"Error checking email verification: {e}")
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
        st.error(f"Error updating last login: {e}")

def send_verification_email(email: str, token: str, app_url: str) -> bool:
    """Send verification email using Resend or placeholder"""
    
    # Detect if we're running locally or on Streamlit Cloud
    import streamlit as st
    try:
        # Try to get the current URL from Streamlit
        current_url = st.get_option("server.baseUrlPath") or "http://localhost:8501"
        if "localhost" in current_url or "127.0.0.1" in current_url:
            # We're running locally
            verification_url = f"http://localhost:8501?verify_token={token}"
        else:
            # We're on Streamlit Cloud, use the provided app_url
            verification_url = f"{app_url}?verify_token={token}"
    except:
        # Fallback to provided app_url
        verification_url = f"{app_url}?verify_token={token}"
    
    # === RESEND EMAIL SERVICE ===
    try:
        import resend
        import os
        
        # Get API key from environment variable
        resend_api_key = os.getenv("RESEND_API_KEY")
        if not resend_api_key:
            st.warning("⚠️ RESEND_API_KEY not configured. Using fallback verification link.")
            # Show the verification URL in the app as fallback
            st.info("🔗 **Manual Verification Link**")
            st.info(f"Since email sending is not configured, please use this link to verify your email:")
            st.markdown(f"**[🚀 Click to Verify Email]({verification_url})**")
            st.code(verification_url, language="text")
            st.warning("⚠️ This link will expire in 10 minutes!")
            return False
        
        resend.api_key = resend_api_key
        
        # For development, use Resend's sandbox domain
        # For production, replace with your verified domain
        from_email = "Acme <onboarding@resend.dev>"  # Resend's sandbox domain
        
        response = resend.Emails.send({
            "from": from_email,
            "to": [email],
            "subject": "Verify your email - Reddit SaaS Idea Finder",
            "html": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">🚀 Welcome to Reddit SaaS Idea Finder!</h2>
                <p>Thanks for signing up! Click the button below to verify your email address and unlock 15 scrapes per day:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" style="background-color: #007bff; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;">
                        ✅ Verify Email Address
                    </a>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    Or copy and paste this link into your browser:<br>
                    <a href="{verification_url}" style="color: #007bff;">{verification_url}</a>
                </p>
                
                <div style="background-color: #fff3cd; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <p style="margin: 0; color: #856404;">
                        ⚠️ <strong>Important:</strong> This verification link will expire in 10 minutes.
                    </p>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    If you didn't request this verification, you can safely ignore this email.
                </p>
            </div>
            """
        })
        
        if response.id:
            st.success(f"✅ Email sent successfully to {email}")
            return True
        else:
            st.error(f"❌ Failed to send email to {email}")
            # Show fallback verification link
            st.info("🔗 **Manual Verification Link**")
            st.info(f"Since email sending failed, please use this link to verify your email:")
            st.markdown(f"**[🚀 Click to Verify Email]({verification_url})**")
            st.code(verification_url, language="text")
            st.warning("⚠️ This link will expire in 10 minutes!")
            return False
            
    except ImportError:
        st.warning("⚠️ Resend not installed. Using fallback verification link.")
        # Show the verification URL in the app as fallback
        st.info("🔗 **Manual Verification Link**")
        st.info(f"Since Resend is not installed, please use this link to verify your email:")
        st.markdown(f"**[🚀 Click to Verify Email]({verification_url})**")
        st.code(verification_url, language="text")
        st.warning("⚠️ This link will expire in 10 minutes!")
        return False
    except Exception as e:
        st.error(f"❌ Resend error: {e}")
        # Show fallback verification link
        st.info("🔗 **Manual Verification Link**")
        st.info(f"Since email sending failed, please use this link to verify your email:")
        st.markdown(f"**[🚀 Click to Verify Email]({verification_url})**")
        st.code(verification_url, language="text")
        st.warning("⚠️ This link will expire in 10 minutes!")
        return False

def handle_verification_flow():
    """Handle the complete verification flow"""
    qs = st.query_params
    
    # Check for verification token in URL
    verify_token_param = qs.get("verify_token")
    
    if verify_token_param:
        # User clicked verification link
        success, email = verify_token(verify_token_param)
        
        if success:
            st.success(f"✅ Email verified successfully! Welcome, {email}")
            st.session_state["user_email"] = email
            st.session_state["is_verified"] = True
            update_last_login(email)
            
            # Store email in URL parameters for persistence across page refreshes
            st.query_params["email"] = email
            
            # Clear the verification token from URL
            st.query_params.pop("verify_token", None)
            st.rerun()
        else:
            st.error("❌ Invalid or expired verification token")
            st.query_params.clear()
            st.rerun()

def get_current_user_email() -> Optional[str]:
    """Get the current verified user's email"""
    return st.session_state.get("user_email")

def is_user_verified() -> bool:
    """Check if current user is verified"""
    return st.session_state.get("is_verified", False)

def sign_out_verified_user():
    """Sign out the verified user"""
    st.session_state.pop("user_email", None)
    st.session_state.pop("is_verified", None)
    
    # Clear email from URL parameters
    st.query_params.pop("email", None)
    
    st.success("✅ Signed out successfully")
    st.rerun() 