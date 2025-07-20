import os, time, streamlit as st
from datetime import datetime, timedelta
from jose import jwt
from supabase import create_client

# Try to get from Streamlit secrets first, then fall back to environment variables
try:
    SB_URL = st.secrets["SUPABASE_URL"]
    SB_KEY = st.secrets["SUPABASE_ANON_KEY"]
    JWT_SECRET = st.secrets.get("JWT_SECRET", "change-me")
except:
    SB_URL = os.getenv("SUPABASE_URL")
    SB_KEY = os.getenv("SUPABASE_ANON_KEY")
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me")

# Only create client if we have the required credentials
if SB_URL and SB_KEY:
    sb = create_client(SB_URL, SB_KEY)
else:
    sb = None

def _jwt(uid, email):
    exp = datetime.utcnow() + timedelta(days=30)
    return jwt.encode({"sub": uid, "email": email, "exp": exp.timestamp()},
                      JWT_SECRET, algorithm="HS256")

def current_user():
    token = st.session_state.get("jwt")
    if not token:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        st.session_state.pop("jwt", None)
        return None

def handle_magic_link():
    if not sb:
        return
    qs = st.query_params
    token = qs.get("access_token", None)
    if not token:
        return
    try:
        user = sb.auth.get_user(token)
        if user and user.user:
            st.session_state["jwt"] = _jwt(user.user.id, user.user.email)
            st.session_state["jwt_user_id"] = user.user.id
            st.rerun()
    except Exception as e:
        st.error(f"Authentication error: {e}")

def require_signup():
    """Show signup form in the main area instead of modal"""
    if not sb:
        st.error("Supabase not configured. Authentication is not available.")
        return False
        
    st.markdown("---")
    st.markdown("## 🔐 Create a Free Account")
    st.markdown("**Get 15 scrapes per day instead of 2!**")
    
    with st.form("signup_form"):
        email = st.text_input("Email", placeholder="your@email.com")
        submit_button = st.form_submit_button("Send Magic Link")
        
        if submit_button and email:
            try:
                sb.auth.sign_in_with_otp({"email": email})
                st.success("✅ Magic link sent! Check your inbox and click the link to sign in.")
                st.info("After clicking the magic link, you'll be redirected back here and automatically signed in.")
            except Exception as e:
                st.error(f"Error sending magic link: {e}")
    
    st.markdown("---")
    return True 