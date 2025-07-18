import os, time, streamlit as st
from datetime import datetime, timedelta
from jose import jwt
from supabase import create_client

SB_URL  = st.secrets["SUPABASE_URL"]
SB_KEY  = st.secrets["SUPABASE_ANON_KEY"]
JWT_SECRET = st.secrets.get("JWT_SECRET", "change‑me")
sb = create_client(SB_URL, SB_KEY)

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
    qs = st.experimental_get_query_params()
    token = qs.get("access_token", [None])[0]
    if not token:
        return
    user = sb.auth.get_user(token)
    if user and user.user:
        st.session_state["jwt"] = _jwt(user.user.id, user.user.email)
        st.experimental_rerun()

def require_signup():
    from streamlit_modal import Modal
    modal = Modal("Create a free account", key="signup_modal")
    with modal.container():
        email = st.text_input("Email", key="signup_email")
        if st.button("Send magic link", key="send_link") and email:
            sb.auth.sign_in(email=email)
            st.success("Check your inbox!")
    st.stop() 