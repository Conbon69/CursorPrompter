#!/usr/bin/env python3
"""
Simple test for email functionality
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_email_send():
    """Test sending a real email"""
    
    print("🧪 Testing Email Send...")
    
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
        
        # Test sending a real email
        test_email = input("Enter your email address to test: ").strip()
        
        if not test_email:
            print("❌ No email provided")
            return False
        
        print(f"📧 Sending test email to {test_email}...")
        
        response = resend.Emails.send({
            "from": "Acme <onboarding@resend.dev>",
            "to": [test_email],
            "subject": "Test Email - Reddit SaaS Idea Finder",
            "html": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">🧪 Test Email</h2>
                <p>This is a test email to verify that the Resend integration is working correctly.</p>
                <p>If you received this email, the email verification system is working!</p>
                <div style="background-color: #d4edda; padding: 15px; border-radius: 6px; margin: 20px 0;">
                    <p style="margin: 0; color: #155724;">
                        ✅ <strong>Success!</strong> Email sending is working correctly.
                    </p>
                </div>
            </div>
            """
        })
        
        print(f"📊 Response: {response}")
        print(f"📊 Response type: {type(response)}")
        print(f"📊 Response attributes: {dir(response)}")
        
        if hasattr(response, 'id') and response.id:
            print("✅ Email sent successfully!")
            print(f"📧 Check your inbox at {test_email}")
            return True
        else:
            print("❌ Email not sent successfully")
            return False
        
    except ImportError as e:
        print(f"❌ Failed to import Resend: {e}")
        print("💡 Run: pip install resend")
        return False
    except Exception as e:
        print(f"❌ Resend error: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Simple Email Test...")
    print("=" * 50)
    
    success = test_email_send()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Email test passed! Resend integration is working.")
    else:
        print("❌ Email test failed. Check the error messages above.") 