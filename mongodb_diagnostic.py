#!/usr/bin/env python3
"""
MongoDB Connection Diagnostic Script
Run this script to diagnose and fix MongoDB connection issues
"""

import os
import sys
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError

def check_environment():
    """Check if environment variables are properly set"""
    print("🔍 Checking environment variables...")
    
    uri = os.environ.get("MONGO_URI")
    
    if not uri:
        print("❌ MONGO_URI is not set")
        print("\nPlease create a .env file with:")
        print("MONGO_URI=mongodb://localhost:27017/annapoorneshwari_tyre_works")
        return False
    
    print(f"✅ MONGO_URI found: {uri[:20]}...")  # Show first 20 chars for security
    return True

def test_connection():
    """Test MongoDB connection"""
    print("\n🔌 Testing MongoDB connection...")
    
    uri = os.environ.get("MONGO_URI")
    
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        
        # Get database info
        db = client['annapoorneshwari_tyre_works']
        collections = db.list_collection_names()
        
        print("✅ Connection successful!")
        print(f"📊 Available collections: {collections}")
        
        client.close()
        return True
        
    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
        print("This usually means the URI format is incorrect")
        return False
        
    except ServerSelectionTimeoutError as e:
        print(f"❌ Connection timeout: {e}")
        print("This usually means the server is unreachable")
        return False
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def create_env_template():
    """Create a .env template file"""
    template = """# MongoDB Configuration
# Replace with your actual MongoDB connection string

# For local MongoDB:
# MONGO_URI=mongodb://localhost:27017/annapoorneshwari_tyre_works

# For MongoDB Atlas:
# MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/annapoorneshwari_tyre_works?retryWrites=true&w=majority

# For testing with MongoDB Memory Server:
# MONGO_URI=mongodb://127.0.0.1:27017/test
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(template)
        print("✅ Created sample .env file")
    else:
        print("ℹ️  .env file already exists")

if __name__ == "__main__":
    print("🔧 MongoDB Connection Diagnostics")
    print("=" * 50)
    
    create_env_template()
    print()
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
    
    if check_environment():
        test_connection()
    
    print("\n" + "=" * 50)
    print("Next steps:")
    print("1. Check your .env file for correct MONGO_URI")
    print("2. Ensure MongoDB is running")
    print("3. Check network connectivity")
