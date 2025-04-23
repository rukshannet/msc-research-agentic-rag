import sys
from pymongo import MongoClient

from config import load_config

def connect_to_mongodb():
    """Connect to MongoDB and return the client."""
    config = load_config()
    try:
        # Verify environment variables are loaded
        if not config["MONGODB_USERNAME"] or not config["MONGODB_PASSWORD"]:
            print("Error: MongoDB credentials not found in environment variables.")
            print("Please make sure MONGODB_USERNAME and MONGODB_PASSWORD are set in your .env file.")
            sys.exit(1)
            
        client = MongoClient(config["MONGODB_URI"], serverSelectionTimeoutMS=30000)
        # Test the connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB")
        return client
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise

def list_available_collections(client):
    """List all available databases and collections."""
    print("\nAvailable databases and collections:")
    for db_name in client.list_database_names():
        if db_name not in ['admin', 'local', 'config']:  # Skip system databases
            db = client[db_name]
            collections = db.list_collection_names()
            print(f"Database: {db_name}")
            for coll in collections:
                count = db[coll].count_documents({})
                print(f"  - Collection: {coll} ({count} documents)")
    print("")