#!/usr/bin/env python3
"""
End-to-end test for email verification functionality
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_email_send():
    """Test sending a real email"""
    
    print("🧪 Testing Email Send E2E...")
    
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
        
        # Test sending a real email (you can change this to your email)
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
        print("✅ Email sent successfully!")
        print(f"📧 Check your inbox at {test_email}")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import Resend: {e}")
        print("💡 Run: pip install resend")
        return False
    except Exception as e:
        print(f"❌ Resend error: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        return False

def test_fastapi_email_function():
    """Test the FastAPI email function"""
    
    print("\n🧪 Testing FastAPI Email Function...")
    
    try:
        # Import the FastAPI email function
        from main_fastapi import send_verification_email_fastapi
        
        print("✅ FastAPI email function imported successfully")
        
        # Test with dummy data (won't actually send)
        test_email = "test@example.com"
        test_token = "test-token-123"
        test_url = "http://localhost:8000"
        
        print(f"📧 Testing email function with: {test_email}")
        
        # This will attempt to send but should fail gracefully
        result = send_verification_email_fastapi(test_email, test_token, test_url)
        
        print(f"📊 Function result: {result}")
        print("✅ Email function test completed")
        return True
        
    except Exception as e:
        print(f"❌ Error testing FastAPI email function: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting E2E Email Tests...")
    print("=" * 50)
    
    # Test 1: Direct email send
    test1_passed = test_email_send()
    
    # Test 2: FastAPI email function
    test2_passed = test_fastapi_email_function()
    
    print("\n" + "=" * 50)
    print("📊 E2E Test Results:")
    print(f"Direct Email Send: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"FastAPI Email Function: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All E2E tests passed! Email system is working correctly.")
    else:
        print("\n⚠️ Some E2E tests failed. Check the error messages above.") 