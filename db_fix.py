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
        print("❌ ERROR: MONGO_URI environment variable is notThe `.env` file cannot be read directly due to restrictions. However, I can infer that the MongoDB connection URI is likely stored in that file as `MONGO_URI`. 

To troubleshoot the connection issue, please check the following:

1. **Verify the URI**: Ensure that the `MONGO_URI` in your `.env` file is correctly formatted and points to a valid MongoDB server. It should look something like this:
   ```
   MONGO_URI=mongodb://username:password@host:port/database
   ```

2. **Network Connectivity**: Make sure that your machine can reach the MongoDB server. You can try pinging the server or using a tool like `telnet` to check if the port is open.

3. **DNS Resolution**: Since the error indicates a DNS timeout, ensure that your DNS settings are correct. You might want to try using a different DNS server (like Google's 8.8.8.8) to see if that resolves the issue.

4. **Firewall Settings**: Check if there are any firewall rules that might be blocking the connection to the MongoDB server.

If you can confirm the URI and check the network settings, I can assist you further based on that information. Would you like to proceed with any specific checks or modifications?
