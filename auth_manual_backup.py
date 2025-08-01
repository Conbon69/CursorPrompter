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



def check_jwt_secret():
    """Check if JWT_SECRET is properly configured"""
    global JWT_SECRET
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔍 JWT_SECRET Check**")
    
    if JWT_SECRET == "change-me":
        st.sidebar.error("❌ JWT_SECRET is using default value 'change-me'")
        st.sidebar.warning("""
        **This will cause authentication failures!**
        
        You need to set the JWT_SECRET in your environment or Streamlit secrets.
        
        **To fix this:**
        1. Get your JWT secret from Supabase dashboard
        2. Add it to your `.env` file: `JWT_SECRET=your_actual_secret`
        3. Or add it to Streamlit secrets
        """)
        return False
    else:
        st.sidebar.success(f"✅ JWT_SECRET configured: {JWT_SECRET[:10]}...")
        return True

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
    """Get current user from Supabase session or custom JWT fallback"""
    # First try Supabase session
    if "user" in st.session_state:
        return st.session_state["user"]
    
    # Fallback to custom JWT (for backward compatibility)
    token = st.session_state.get("jwt")
    if token:
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            st.session_state.pop("jwt", None)
        except Exception:
            st.session_state.pop("jwt", None)
    
    return None

def get_supabase_session():
    """Get current Supabase session"""
    return st.session_state.get("supabase_session")

def is_authenticated():
    """Check if user is authenticated with Supabase"""
    return "user" in st.session_state and st.session_state["user"] is not None

def get_user_id():
    """Get current user ID from Supabase session or fallback"""
    user = current_user()
    if user and hasattr(user, 'id'):
        return user.id
    return st.session_state.get("jwt_user_id", "anonymous")

def initialize_auth():
    """Initialize authentication state on app startup"""
    if not sb:
        return
    
    # Check if we have a stored session
    session = get_supabase_session()
    if session:
        try:
            # Try to get current user to validate session
            user = sb.auth.get_user()
            if user and user.user:
                st.session_state["user"] = user.user
                return
        except:
            # Session expired, clear it
            st.session_state.pop("supabase_session", None)
            st.session_state.pop("user", None)
    
    # Check for URL parameters (magic link redirect)
    handle_magic_link()

def handle_magic_link():
    """Handle magic link authentication using proper Supabase session management"""
    if not sb:
        return
    
    qs = st.query_params
    
    # Check for both access_token and refresh_token
    access_token = qs.get("access_token")
    refresh_token = qs.get("refresh_token")
    
    if access_token and refresh_token:
        try:
            st.sidebar.info("🔍 Setting up authentication session...")
            # Set the session using both tokens
            session = sb.auth.set_session(access_token, refresh_token)
            
            if session and session.user:
                # Store the session in Streamlit state
                st.session_state["supabase_session"] = session
                st.session_state["user"] = session.user
                st.sidebar.success(f"✅ Authenticated as {session.user.email}")
                st.rerun()
            else:
                st.sidebar.error("❌ Failed to establish session")
                
        except Exception as e:
            st.sidebar.error(f"❌ Authentication error: {e}")
    
    elif access_token:
        # Fallback: if only access_token is present, try to get user directly
        try:
            st.sidebar.info("🔍 Attempting authentication with access token...")
            user = sb.auth.get_user(access_token)
            if user and user.user:
                st.session_state["user"] = user.user
                st.sidebar.success(f"✅ Authenticated as {user.user.email}")
                st.rerun()
        except Exception as e:
            st.sidebar.error(f"❌ Authentication error: {e}")
    
    # If no tokens found, show manual token input as fallback
    if not access_token and not refresh_token:
        st.sidebar.warning("🔍 No authentication tokens found in URL.")
        
        # Show helpful instructions for URL fragment extraction
        st.sidebar.markdown("**🔧 Magic Link Token Extraction**")
        st.sidebar.markdown("""
        If you just clicked a magic link and see a URL like:
        `http://localhost:8501/#access_token=eyJhbGciOiJIUzI1NiIs...`
        
        **The token is in the URL fragment (after #). Please:**
        1. Look at your browser's address bar
        2. Find the part after `#access_token=`
        3. Copy the entire token (starts with `eyJhbGciOiJIUzI1NiIs...`)
        4. Paste it in the input below
        """)
        
        # Show a prominent input for the token
        fragment_token = st.sidebar.text_input(
            "🔐 Paste your access token from the URL:",
            placeholder="eyJhbGciOiJIUzI1NiIs...",
            help="Copy the token from your browser's address bar after clicking the magic link"
        )
        
        if fragment_token and st.sidebar.button("🔐 Authenticate with Token", use_container_width=True):
            authenticate_with_token(fragment_token)

def check_for_url_fragment_token():
    """Check if there's a token in the URL fragment and provide easy authentication"""
    # Check if user is already authenticated
    user = current_user()
    if user:
        return  # Already authenticated
    
    # Show a prominent message if we detect this might be a magic link redirect
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔐 Magic Link Authentication**")
    st.sidebar.markdown("""
    **Did you just click a magic link?**
    
    If your URL looks like this:
    `http://localhost:8501/#access_token=eyJhbGciOiJIUzI1NiIs...`
    
    **Quick Authentication:**
    1. Copy the token from your address bar (after `#access_token=`)
    2. Paste it below
    3. Click "Sign In with Token"
    """)
    
    # Provide a simple one-click authentication
    token_input = st.sidebar.text_input(
        "🔑 Access Token:",
        placeholder="eyJhbGciOiJIUzI1NiIs...",
        help="Paste the token from your browser's address bar"
    )
    
    if st.sidebar.button("🚀 Sign In with Token", use_container_width=True, type="primary"):
        if token_input:
            authenticate_with_token(token_input)
        else:
            st.sidebar.error("Please paste the token from your URL")
    
    # Also show a helpful tip
    st.sidebar.info("💡 **Tip:** The token is the long string that starts with `eyJ` in your address bar")


def authenticate_with_token(token):
    """Authenticate with a given token"""
    try:
        st.sidebar.info(f"🔍 Attempting to authenticate...")
        
        # This is a JWT token, so we can use get_user
        user = sb.auth.get_user(token)
        
        if user and user.user:
            st.sidebar.success(f"✅ Authentication successful for {user.user.email}")
            st.session_state["jwt"] = _jwt(user.user.id, user.user.email)
            st.session_state["jwt_user_id"] = user.user.id
            st.rerun()
        else:
            st.sidebar.error("❌ User data not found in response")
            
    except Exception as e:
        st.sidebar.error(f"❌ Authentication error: {e}")

def require_signup():
    """Show signup form with manual token instructions"""
    if not sb:
        st.error("Supabase not configured. Authentication is not available.")
        return False
        
    st.markdown("---")
    st.markdown("## 🔐 Create a Free Account")
    st.markdown("**Get 15 scrapes per day instead of 2!**")
    
    # Show current authentication status
    user = current_user()
    if user:
        st.success(f"✅ Already signed in as: {user.get('email', 'Unknown')}")
        if st.button("🔄 Refresh Status"):
            st.rerun()
        return True
    
    with st.form("signup_form"):
        email = st.text_input("Email", placeholder="your@email.com")
        submit_button = st.form_submit_button("Send Magic Link")
        
        if submit_button and email:
            try:
                st.info(f"🔍 Sending magic link to {email}...")
                
                # Get the current URL for redirect
                current_url = st.get_option("server.baseUrlPath") or "http://localhost:8501"
                
                # Send magic link with proper redirect configuration
                response = sb.auth.sign_in_with_otp({
                    "email": email,
                    "options": {
                        "emailRedirectTo": current_url
                    }
                })
                
                st.success("✅ Magic link sent! Check your inbox and click the link to sign in.")
                st.info("After clicking the magic link, you'll be redirected back here and automatically signed in.")
                st.warning("⚠️ If the magic link doesn't redirect properly, you can manually copy the token from the verification page and paste it in the sidebar.")
                
                # Debug: Show response details
                st.write("🔍 Response details:", response)
                
            except Exception as e:
                st.error(f"❌ Error sending magic link: {e}")
                st.write("🔍 Full error details:", str(e))
    
    st.markdown("---")
    return True

def sign_out():
    """Sign out and clear all session data"""
    if sb:
        try:
            sb.auth.sign_out()
        except:
            pass
    
    # Clear all session state
    for key in ["supabase_session", "user", "jwt", "jwt_user_id"]:
        st.session_state.pop(key, None)
    
    st.success("✅ Signed out successfully")
    st.rerun() 