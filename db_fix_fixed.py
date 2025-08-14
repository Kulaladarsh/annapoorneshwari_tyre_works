"""
MongoDB Connection Fix and Diagnostics
Run this file to test your MongoDB connection
"""

import os
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError
import sys

def test_mongodb_connection():
    """Test MongoDB connection and provide diagnostics"""
    
    # Get MongoDB URI from environment
    uri = os.environ.get("MONGO_URI")
    
    if not uri:
        print("❌ ERROR: MONGO_URI environment variable is not set")
        print("Please check your .env file and ensure it contains:")
        print("MONGO_URI=mongodb://username:password@host:port/database")
        return False
    
    print(f"🔍 Testing connection with URI: {uri}")
    
    try:
        # Test connection with timeout
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        
        # Force a connection attempt
        client.admin.command('ping')
        
        # Get database info
        db_names = client.list_database_names()
        print("✅ Successfully connected to MongoDB!")
        print(f"📊 Available databases: {db_names}")
        
        # Test specific database
        db = client['annapoorneshwari_tyre_works']
        collections = db.list_collection_names()
        print(f"📁 Collections in annapoorneshwari_tyre_works: {collections}")
        
        client.close()
        return True
        
    except ConfigurationError as e:
        print(f"❌ Configuration Error: {e}")
        print("This usually means the URI format is incorrect")
        return False
        
    except ServerSelectionTimeoutError as e:
        print(f"❌ Connection Timeout: {e}")
        print("This usually means the server is unreachable")
        print("Check:")
        print("1. Your internet connection")
        print("2. MongoDB server status")
        print("3. Firewall settings")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def create_sample_env():
    """Create a sample .env file if it doesn't exist"""
    env_content = """# MongoDB Configuration
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
            f.write(env_content)
        print("✅ Created sample .env file")
    else:
        print("ℹ️  .env file already exists")

if __name__ == "__main__":
    print("🔧 MongoDB Connection Diagnostics")
    print("=" * 50)
    
    create_sample_envIt seems there was an issue with the editing process. I will rewrite the `db_fix.py` file from scratch to ensure it contains the correct content without any syntax errors.

<create_file>
<path>db_fix.py</path>
<content>
"""
MongoDB Connection Fix and Diagnostics
Run this file to test your MongoDB connection
"""

import os
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError
import sys
from dotenv import load_dotenv

def test_mongodb_connection():
    """Test MongoDB connection and provide diagnostics"""
    
    # Get MongoDB URI from environment
    uri = os.environ.get("MONGO_URI")
    
    if not uri:
        print("❌ ERROR: MONGO_URI environment variable is not set")
        print("Please check your .env file and ensure it contains:")
        print("MONGO_URI=mongodb://username:password@host:port/database")
        return False
    
    print(f"🔍 Testing connection with URI: {uri}")
    
    try:
        # Test connection with timeout
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        
        # Force a connection attempt
        client.admin.command('ping')
        
        # Get database info
        db_names = client.list_database_names()
        print("✅ Successfully connected to MongoDB!")
        print(f"📊 Available databases: {db_names}")
        
        # Test specific database
        db = client['annapoorneshwari_tyre_works']
        collections = db.list_collection_names()
        print(f"📁 Collections in annapoorneshwari_tyre_works: {collections}")
        
        client.close()
        return True
        
    except ConfigurationError as e:
        print(f"❌ Configuration Error: {e}")
        print("This usually means the URI format is incorrect")
        return False
        
    except ServerSelectionTimeoutError as e:
        print(f"❌ Connection Timeout: {e}")
        print("This usually means the server is unreachable")
        print("Check:")
        print("1. Your internet connection")
        print("2. MongoDB server status")
        print("3. Firewall settings")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def create_sample_env():
    """Create a sample .env file if it doesn't exist"""
    env_content = """# MongoDB Configuration
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
            f.write(env_content)
        print("✅ Created sample .env file")
    else:
        print("ℹ️  .env file already exists")

if __name__ == "__main__":
    print("🔧 MongoDB Connection Diagnostics")
    print("=" * 50)
    
    create_sample_env()
    print()
    
    # Load environment variables
    load_dotenv()
    
    test_mongodb_connection()
