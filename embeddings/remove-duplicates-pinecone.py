import argparse
from pinecone import Pinecone
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Pinecone Configuration
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME')

def connect_to_pinecone(index_name=None):
    """Connect to Pinecone and return the index."""
    try:
        # Initialize Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # Use provided index name or default
        if not index_name:
            index_name = PINECONE_INDEX_NAME
        
        # Check if index exists
        existing_indexes = pc.list_indexes()
        index_names = [index.name for index in existing_indexes] if existing_indexes else []
        
        if index_name not in index_names:
            print(f"Error: Index '{index_name}' not found in Pinecone.")
            return None
        
        # Connect to the index
        index = pc.Index(index_name)
        print(f"Connected to Pinecone index: {index_name}")
        return index
    except Exception as e:
        print(f"Failed to connect to Pinecone: {e}")
        return None

def fetch_all_metadata(index, batch_size=1000):
    """Fetch metadata from all records in Pinecone database."""
    try:
        # Get index statistics
        stats = index.describe_index_stats()
        total_vectors = stats.total_vector_count
        print(f"\nIndex Statistics:")
        print(f"Total vectors: {total_vectors}")
        print(f"Dimension: {stats.dimension}")
        
        # Create a dummy vector for querying
        dummy_vector = [0.0] * stats.dimension
        
        # Since Pinecone doesn't have a direct "fetch all" functionality,
        # we need to implement pagination using a combination of query and fetch
        
        all_results = []
        processed_ids = set()
        record_count = 0
        
        print("\nRetrieving all records. This may take some time...")
        
        # Estimate number of batches
        num_batches = (total_vectors + batch_size - 1) // batch_size
        
        # Set for already seen IDs to avoid duplicates
        seen_ids = set()
        
        # First batch with dummy vector
        response = index.query(
            vector=dummy_vector,
            top_k=batch_size,
            include_metadata=True,
            include_values=False
        )
        
        # Extract results
        for match in response.matches:
            if match.id not in seen_ids:
                seen_ids.add(match.id)
                record_count += 1
                
                if hasattr(match, 'metadata') and match.metadata:
                    title = match.metadata.get('title', 'No title available')
                    url = match.metadata.get('url', 'No URL available')
                    
                    print(f"\nRecord {record_count}:")
                    print(f"ID: {match.id}")
                    print(f"Title: {title}")
                    print(f"URL: {url}")
                    
                    all_results.append({
                        'id': match.id,
                        'title': title,
                        'url': url
                    })
                else:
                    print(f"\nRecord {record_count}:")
                    print(f"ID: {match.id}")
                    print("Title: No metadata available")
                    print("URL: No metadata available")
        
        # If we still have more records than we've retrieved, try alternative approaches
        if record_count < total_vectors:
            print(f"\nInitial batch retrieved {record_count} records out of {total_vectors}.")
            print("Note: Pinecone doesn't provide a direct method to paginate through all vectors.")
            print("Consider using ID prefixes or namespaces if you need to retrieve all records.")
            
            # You can add additional strategies here if needed, such as:
            # 1. Using ID prefixes if your IDs follow a pattern
            # 2. Querying by namespaces if you use namespaces in your index
            # 3. Using filter expressions if your metadata has fields you can filter on
        
        print(f"\nRetrieved a total of {record_count} records.")
        return all_results
            
    except Exception as e:
        print(f"Error fetching records: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Retrieve all IDs, titles, and URLs from Pinecone')
    parser.add_argument('--index', type=str, help='Name of the Pinecone index')
    parser.add_argument('--batch-size', type=int, default=1000, 
                        help='Batch size for retrieving records (max 10000)')
    args = parser.parse_args()
    
    # Connect to Pinecone
    index = connect_to_pinecone(args.index)
    if not index:
        return
    
    # Fetch all metadata
    fetch_all_metadata(index, args.batch_size)

if __name__ == "__main__":
    main()
