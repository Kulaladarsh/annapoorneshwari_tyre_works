"""
MongoDB Connection Fix for Annapoorneshwari Tyre Works
This file provides a robust MongoDB connection setup
"""

import os
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBConnection:
    """Robust MongoDB connection handler"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.uri = None
        
    def connect(self):
        """Establish MongoDB connection with error handling"""
        try:
            # Get MongoDB URI from environment
            self.uri = os.environ.get("MONGO_URI")
            
            if not self.uri:
                logger.error("MONGO_URI environment variable is not set")
                return False
            
            # Create connection with timeout
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            # Get database
            self.db = self.client['annapoorneshwari_tyre_works']
            
            logger.info("✅ Successfully connected to MongoDB")
            return True
            
        except ConfigurationError as e:
            logger.error(f"❌ Configuration Error: {e}")
            return False
        except ServerSelectionTimeoutError as e:
            logger.error(f"❌ Connection Timeout: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def get_database(self):
        """Get database instance"""
        return self.db
    
    def close(self):
        """Close connection"""
        if self.client:
            self.client.close()
            logger.info("🔌 MongoDB connection closed")

# Global connection instance
mongo_conn = MongoDBConnection()

def init_db():
    """Initialize database connection"""
    if mongo_conn.connect():
        return mongo_conn.get_database()
    else:
        # Fallback to local development settings
        logger.warning("Using fallback MongoDB settings")
        try:
            # Try local MongoDB
            client = MongoClient('mongodb://localhost:27017/')
            return client['annapoorneshwari_tyre_works']
        except:
            logger.error("Failed to connect to any MongoDB instance")
            return None

# Initialize database
db = init_db()

# Export collections
if db:
    services_collection = db['services']
    ratings_collection = db['get_ratings']
    prebookings_collection = db['prebookings']
    admin_collection = db['admins']
    otp_collection = db['otps']
    payments_collection = db['payments']
    painting_limits_collection = db['painting_limits']
else:
    logger.error("Database not initialized")
    # Create mock collections for development
    services_collection = None
    ratings_collection = None
    prebookings_collection = None
    admin_collection = None
    otp_collection = None
    payments_collection = None
    painting_limits_collection = None
