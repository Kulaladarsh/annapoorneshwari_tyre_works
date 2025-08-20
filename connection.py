import os
from pymongo import MongoClient

def get_database():
    """Get MongoDB database connection"""
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise ValueError("MONGO_URI environment variable is not set")
    
    client = MongoClient(uri)
    # Use 'annapoorneshwari_tyre_works' as the database name
    db = client['annapoorneshwari_tyre_works']
    return db
