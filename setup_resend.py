#!/usr/bin/env python3
"""
Setup Resend API Key for email verification
"""

import os
import sys

def setup_resend():
    """Setup Resend API key for email verification"""
    
    print("🔐 Resend Email Setup for Reddit SaaS Idea Finder")
    print("=" * 50)
    
    # Check if .env file exists
    env_file = '.env'
    if not os.path.exists(env_file):
        print("📝 Creating .env file...")
        with open(env_file, 'w') as f:
            f.write("# Environment variables for Reddit SaaS Idea Finder\n")
    
    # Read current .env file
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Check if RESEND_API_KEY already exists
    if 'RESEND_API_KEY' in content:
        print("✅ RESEND_API_KEY already exists in .env file")
        
        # Show current value (masked)
        lines = content.split('\n')
        for line in lines:
            if line.startswith('RESEND_API_KEY='):
                key_value = line.split('=', 1)[1].strip()
                if key_value:
                    masked_key = key_value[:10] + '...' if len(key_value) > 10 else '***'
                    print(f"   Current key: {masked_key}")
                else:
                    print("   Current key: (empty)")
                break
        
        # Ask if user wants to update
        update = input("\n🔄 Do you want to update the RESEND_API_KEY? (y/N): ").strip().lower()
        if update != 'y':
            print("✅ Keeping existing key.")
            return
    
    print("\n📧 To get your Resend API key:")
    print("1. Go to https://resend.com")
    print("2. Sign up or log in")
    print("3. Go to API Keys in the dashboard")
    print("4. Click 'Create API Key'")
    print("5. Give it a name like 'Reddit SaaS Finder'")
    print("6. Copy the API key (starts with 're_')")
    print()
    
    # Get API key from user
    api_key = input("🔑 Enter your Resend API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided. Setup cancelled.")
        return
    
    if not api_key.startswith('re_'):
        print("⚠️  Warning: API key doesn't start with 're_'. Are you sure this is correct?")
        confirm = input("Continue anyway? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Setup cancelled.")
            return
    
    # Update .env file
    lines = content.split('\n')
    new_lines = []
    key_updated = False
    
    for line in lines:
        if line.startswith('RESEND_API_KEY='):
            new_lines.append(f'RESEND_API_KEY={api_key}')
            key_updated = True
        else:
            new_lines.append(line)
    
    if not key_updated:
        # Add new key at the end
        new_lines.append(f'RESEND_API_KEY={api_key}')
    
    # Write back to .env file
    with open(env_file, 'w') as f:
        f.write('\n'.join(new_lines))
    
    print(f"\n✅ RESEND_API_KEY added to {env_file}!")
    print("🔄 Please restart your Streamlit app for the changes to take effect.")
    print("\n🚀 To test the setup:")
    print("1. Run: streamlit run streamlit_app_new.py")
    print("2. Click '🔐 Verify Email' in the sidebar")
    print("3. Enter your email and click 'Send Verification Email'")
    print("4. Check if email is sent or if fallback link is shown")

if __name__ == "__main__":
    setup_resend() 