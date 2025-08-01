#!/usr/bin/env python3
"""
Add RESEND_API_KEY to .env file
"""

import os

def add_resend_key():
    """Add RESEND_API_KEY to .env file if it doesn't exist"""
    
    print("🔍 Checking .env file for RESEND_API_KEY...")
    
    if not os.path.exists('.env'):
        print("❌ .env file not found. Creating one...")
        with open('.env', 'w') as f:
            f.write("# Environment variables\n")
    
    # Read current .env file
    with open('.env', 'r') as f:
        content = f.read()
    
    # Check if RESEND_API_KEY already exists
    if 'RESEND_API_KEY' in content:
        print("✅ RESEND_API_KEY already exists in .env file")
        return
    
    # Add RESEND_API_KEY
    print("📝 Adding RESEND_API_KEY to .env file...")
    
    # Get API key from user
    print("\n🔑 Please enter your Resend API key:")
    print("   (Get it from https://resend.com/api-keys)")
    print("   (It should start with 're_')")
    
    api_key = input("RESEND_API_KEY: ").strip()
    
    if not api_key:
        print("❌ No API key provided. Skipping...")
        return
    
    if not api_key.startswith('re_'):
        print("⚠️  Warning: API key doesn't start with 're_'. Are you sure this is correct?")
        confirm = input("Continue anyway? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Aborted.")
            return
    
    # Append to .env file
    with open('.env', 'a') as f:
        f.write(f"\n# Resend API Key for email verification\nRESEND_API_KEY={api_key}\n")
    
    print("✅ RESEND_API_KEY added to .env file!")
    print("🔄 Please restart your FastAPI app for the changes to take effect.")

if __name__ == "__main__":
    add_resend_key() 