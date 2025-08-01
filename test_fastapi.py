#!/usr/bin/env python3
"""
Simple test script for the FastAPI app
"""

import requests
import time

def test_fastapi_app():
    """Test the FastAPI app endpoints"""
    
    base_url = "http://localhost:8000"
    
    print("🧪 Testing FastAPI app...")
    
    # Test 1: GET / (should return the form)
    try:
        response = requests.get(base_url)
        if response.status_code == 200:
            print("✅ GET / - Form page loads successfully")
            if "Reddit SaaS Idea Finder" in response.text:
                print("✅ Form contains expected title")
            else:
                print("❌ Form missing expected title")
        else:
            print(f"❌ GET / - Status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ GET / - Could not connect to server (is it running?)")
        return False
    
    # Test 2: POST /scrape with invalid data (should show error)
    try:
        response = requests.post(base_url + "/scrape", data={
            "subreddits": "",
            "posts_per_subreddit": "3",
            "comments_per_post": "10"
        })
        if response.status_code == 200:
            if "Please enter at least one subreddit" in response.text:
                print("✅ POST /scrape - Properly handles empty subreddits")
            else:
                print("❌ POST /scrape - Missing error message for empty subreddits")
        else:
            print(f"❌ POST /scrape - Status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ POST /scrape - Could not connect to server")
        return False
    
    print("🎉 All tests completed!")
    return True

if __name__ == "__main__":
    print("🚀 Starting FastAPI app test...")
    print("Make sure to run 'python main_fastapi.py' in another terminal first!")
    print()
    
    test_fastapi_app() 