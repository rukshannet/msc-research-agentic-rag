import sys
from pinecone import Pinecone, ServerlessSpec

from config import load_config

def initialize_pinecone(index_name=None, cloud=None, region=None):
    """Initialize Pinecone client and return the index."""
    config = load_config()
    
    # Use provided values or defaults from config
    pinecone_index_name = index_name or config["PINECONE_INDEX_NAME"]
    pinecone_cloud = cloud or config["PINECONE_CLOUD"]
    pinecone_region = region or config["PINECONE_REGION"]
    
    try:
        # Verify API key is loaded
        if not config["PINECONE_API_KEY"]:
            print("Error: Pinecone API key not found in environment variables.")
            print("Please make sure PINECONE_API_KEY is set in your .env file.")
            sys.exit(1)
            
        # Initialize Pinecone with the new API format
        pc = Pinecone(api_key=config["PINECONE_API_KEY"])
        
        # Check if index exists
        existing_indexes = pc.list_indexes()
        index_names = [index.name for index in existing_indexes] if existing_indexes else []
        
        if pinecone_index_name not in index_names:
            print(f"Creating new Pinecone index: {pinecone_index_name}")
            # Create a new index with ServerlessSpec
            pc.create_index(
                name=pinecone_index_name,
                dimension=768,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=pinecone_cloud,
                    region=pinecone_region
                )
            )
            print(f"Index {pinecone_index_name} created successfully")
        else:
            print(f"Using existing index: {pinecone_index_name}")
        
        # Connect to the index with the new API format
        index = pc.Index(pinecone_index_name)
        return index
    except Exception as e:
        print(f"Failed to initialize Pinecone: {e}")
        raise