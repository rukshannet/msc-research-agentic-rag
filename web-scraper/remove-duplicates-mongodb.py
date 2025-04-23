import os
import time
from pymongo import MongoClient
from pymongo.server_api import ServerApi

def connect_to_mongodb():
    """Connect to MongoDB using credentials from environment variables"""
    db_username = os.getenv('MONGODB_USERNAME')
    db_password = os.getenv('MONGODB_PASSWORD')
    
    if not db_username or not db_password:
        print("MongoDB credentials not found in environment variables.")
        return None
    
    uri = f"mongodb+srv://{db_username}:{db_password}@ircw.371s5.mongodb.net/?retryWrites=true&w=majority&appName=IRCW"
    client = MongoClient(uri, server_api=ServerApi('1'))
    
    # Test connection
    try:
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def remove_duplicates_for_collection(db_name, collection_name, client):
    """Remove duplicates from a specific collection based on URL property"""
    print(f"\n{'='*80}")
    print(f"Processing {db_name}.{collection_name}")
    print(f"{'='*80}")
    
    # Get database and collection
    db = client[db_name]
    collection = db[collection_name]
    
    # Count total documents and get collection stats
    total_docs = collection.count_documents({})
    print(f"Total documents before deduplication: {total_docs}")
    
    # Find all unique URLs in the collection
    start_time = time.time()
    print("Finding all unique URLs...")
    unique_urls = collection.distinct('url')
    url_count = len(unique_urls)
    print(f"Found {url_count} unique URLs in {time.time() - start_time:.2f} seconds")
    
    # For each unique URL, keep the first document and remove the rest
    duplicates_removed = 0
    processed = 0
    start_time = time.time()
    
    print("\nStarting duplicate removal process...")
    print("-" * 50)
    
    for url in unique_urls:
        # Find all documents with this URL
        docs_with_url = list(collection.find({'url': url}))
        
        if len(docs_with_url) > 1:
            # Keep the first document (docs_with_url[0])
            # Get IDs of all other documents with the same URL
            duplicate_ids = [doc['_id'] for doc in docs_with_url[1:]]
            
            # Remove the duplicates
            delete_result = collection.delete_many({'_id': {'$in': duplicate_ids}})
            removed = delete_result.deleted_count
            duplicates_removed += removed
            
            print(f"URL {processed+1}/{url_count}: Removed {removed} duplicates for: {url[:60]}...")
        
        processed += 1
        
        # Show progress every 100 URLs or for the last URL
        if processed % 100 == 0 or processed == url_count:
            elapsed = time.time() - start_time
            percent_complete = (processed / url_count) * 100
            estimated_total = elapsed / (processed / url_count) if processed > 0 else 0
            remaining = estimated_total - elapsed
            
            print(f"Progress: {processed}/{url_count} URLs processed ({percent_complete:.1f}%)")
            print(f"Time elapsed: {elapsed:.1f}s, Est. remaining: {remaining:.1f}s")
            print(f"Duplicates removed so far: {duplicates_removed}")
            print("-" * 30)
    
    # Count documents after deduplication
    remaining_docs = collection.count_documents({})
    
    print("\nDeduplication complete for this collection!")
    print("-" * 50)
    print(f"Total duplicates removed: {duplicates_removed}")
    print(f"Documents before: {total_docs}")
    print(f"Documents after: {remaining_docs}")
    print(f"Reduction: {((total_docs - remaining_docs) / total_docs * 100):.1f}% (if 0.0%, no duplicates were found)")
    print(f"Total time: {time.time() - start_time:.2f} seconds")
    
    return duplicates_removed

def remove_duplicates_all_collections():
    """Remove duplicates from all news collections"""
    # Connect to MongoDB
    client = connect_to_mongodb()
    
    if client is None:
        print("Failed to connect to MongoDB. Exiting.")
        return
    
    try:
        # Define all database and collection pairs to process
        collections_to_process = [
            ("newsfirst_data", "articles"),
            ("newswire_data", "articles"),
            ("adaderana_data", "articles")
        ]
        
        # Track total duplicates removed across all collections
        total_duplicates_removed = 0
        overall_start_time = time.time()
        
        # Process each collection
        for db_name, collection_name in collections_to_process:
            try:
                duplicates_removed = remove_duplicates_for_collection(db_name, collection_name, client)
                total_duplicates_removed += duplicates_removed
            except Exception as e:
                print(f"Error processing {db_name}.{collection_name}: {e}")
        
        # Print overall summary
        overall_time = time.time() - overall_start_time
        print("\n" + "="*80)
        print("DEDUPLICATION COMPLETE FOR ALL COLLECTIONS")
        print("="*80)
        print(f"Total duplicates removed across all collections: {total_duplicates_removed}")
        print(f"Total processing time: {overall_time:.2f} seconds")
        
    finally:
        # Close the connection
        if client is not None:
            client.close()
            print("\nMongoDB connection closed.")

if __name__ == "__main__":
    remove_duplicates_all_collections()