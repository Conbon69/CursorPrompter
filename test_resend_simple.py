#!/usr/bin/env python3
"""
Simple Resend test following the official documentation
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_resend_simple():
    """Test Resend with the exact example from documentation"""
    
    print("🧪 Testing Resend Simple...")
    
    # Check environment variable
    resend_api_key = os.getenv("RESEND_API_KEY")
    print(f"RESEND_API_KEY: {'✅ Set' if resend_api_key else '❌ Missing'}")
    
    if not resend_api_key:
        print("❌ RESEND_API_KEY not found in environment variables")
        return False
    
    try:
        # Test Resend import
        import resend
        print("✅ Resend library imported successfully")
        
        # Set API key
        resend.api_key = resend_api_key
        print("✅ Resend API key set successfully")
        
        # Test with the exact example from documentation
        print("📧 Testing with documentation example...")
        
        params = {
            "from": "Acme <onboarding@resend.dev>",
            "to": ["delivered@resend.dev"],  # This is Resend's test email
            "subject": "hello world",
            "html": "<strong>it works!</strong>",
        }
        
        print(f"📝 Sending with params: {params}")
        
        email = resend.Emails.send(params)
        print(f"📊 Response: {email}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import Resend: {e}")
        print("💡 Run: pip install resend")
        return False
    except Exception as e:
        print(f"❌ Resend error: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Simple Resend Test...")
    print("=" * 50)
    
    success = test_resend_simple()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Resend test passed! API is working.")
    else:
        print("❌ Resend test failed. Check the error messages above.") 