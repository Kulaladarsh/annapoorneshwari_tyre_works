import requests
import time

def test_otp_functionality():
    """Test the OTP functionality by simulating a login"""

    base_url = "http://localhost:5000"

    # Test data
    test_email = "test@example.com"
    test_password = "test123"

    print("🧪 Testing OTP Functionality")
    print("=" * 50)

    try:
        # Step 1: Attempt login with test credentials
        print(f"1. Attempting login with email: {test_email}")

        login_data = {
            'email': test_email,
            'password': test_password
        }

        response = requests.post(f"{base_url}/login", data=login_data, allow_redirects=False)

        print(f"   Status Code: {response.status_code}")

        if response.status_code == 302:  # Redirect to OTP page
            print("   ✅ Login successful - redirected to OTP page")
            print("   📧 OTP should be printed in the console above")
            print("   🔍 Check the Flask app console output for the OTP")
        elif response.status_code == 200:
            # Check if it's the login page with error message
            if "Invalid email or password" in response.text:
                print("   ❌ Invalid credentials (expected for test user)")
            else:
                print("   ⚠️  Unexpected response - check login page")
        else:
            print(f"   ❌ Unexpected status code: {response.status_code}")

        # Step 2: Check if app is running
        print("\n2. Checking if app is responding...")
        health_response = requests.get(f"{base_url}/health")
        if health_response.status_code == 200:
            print("   ✅ App is running and healthy")
        else:
            print(f"   ❌ Health check failed: {health_response.status_code}")

        print("\n" + "=" * 50)
        print("📋 MANUAL TESTING REQUIRED:")
        print("1. Open browser to http://localhost:5000/login")
        print("2. Try logging in with any email/password")
        print("3. Check Flask console for OTP output")
        print("4. Verify OTP is 6 digits and printed clearly")
        print("=" * 50)

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask app. Is it running?")
        print("   Make sure 'python app.py' is running in another terminal")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    test_otp_functionality()
