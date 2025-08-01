#!/usr/bin/env python3
"""
Check .env file contents directly
"""

import os

print("🔍 Checking .env file directly...")

# Check if .env file exists
if os.path.exists('.env'):
    print("✅ .env file exists")
    
    # Read the file directly
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"📄 File size: {len(content)} characters")
            print("📄 File contents:")
            print("-" * 50)
            print(content)
            print("-" * 50)
            
            # Check for RESEND_API_KEY specifically
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if 'RESEND_API_KEY' in line:
                    print(f"🎯 Found RESEND_API_KEY on line {i}: {line[:30]}...")
                    if '=' in line:
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            print(f"   Key: '{key}'")
                            print(f"   Value: '{value[:10]}...' (length: {len(value)})")
                        else:
                            print(f"   ❌ Invalid format: {line}")
                    else:
                        print(f"   ❌ No '=' found: {line}")
                        
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
else:
    print("❌ .env file does not exist")

print("\n🔍 Current environment variables:")
for key, value in os.environ.items():
    if 'RESEND' in key.upper():
        print(f"  {key}: {value[:10] if value else 'None'}...") 