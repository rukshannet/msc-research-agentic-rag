import os
import sys
import argparse
import time
from dotenv import load_dotenv

# Import modules from local files
from config import load_config
from embeddings.mongo_client import connect_to_mongodb, list_available_collections
from pinecone_client import initialize_pinecone
from embeddings.entity_extraction_local import initialize_entity_extraction_agent
from migration import migrate_collection_to_pinecone

# Load environment variables
load_dotenv()

def parse_arguments():
    """Parse command line arguments."""
    config = load_config()
    
    parser = argparse.ArgumentParser(description='Migrate data from MongoDB collections to Pinecone vector database.')
    
    parser.add_argument('--collections', nargs='+', 
                        help='Specific collections to process in format "db_name.collection_name". Example: --collections newsfirst_data.articles newswire_data.articles')
    
    parser.add_argument('--batch-size', type=int, default=50,
                        help='Batch size for Pinecone upsert operations (default: 50)')
    
    parser.add_argument('--index-name', type=str, default=None,
                        help=f'Name of the Pinecone index to use (default: {config["PINECONE_INDEX_NAME"]})')
    
    parser.add_argument('--cloud', type=str, default=None,
                        help=f'Pinecone cloud provider (default: {config["PINECONE_CLOUD"]})')
    
    parser.add_argument('--region', type=str, default=None,
                        help=f'Pinecone region (default: {config["PINECONE_REGION"]})')
    
    parser.add_argument('--list-only', action='store_true',
                        help='Only list available collections without performing migration')
                        
    parser.add_argument('--resume-from', type=str, default=None,
                        help='Resume from a specific database.collection. Example: --resume-from adaderana_data.articles')
                        
    parser.add_argument('--resume-id', type=str, default=None,
                        help='Resume from a specific document ID. Example: --resume-id 60f1a2b3c4d5e6f7g8h9i0j1')
    
    parser.add_argument('--cursor-batch-size', type=int, default=100,
                        help='Batch size for MongoDB cursor (default: 100, smaller values reduce timeout risk)')
    
    parser.add_argument('--skip-entity-extraction', action='store_true',
                        help='Skip entity extraction even if OpenAI API key is available')
    
    return parser.parse_args()

def main():
    print("Starting migration from MongoDB collections to Pinecone...")
    config = load_config()
    
    try:
        # Make sure environment variables are properly loaded
        required_vars = ['MONGODB_USERNAME', 'MONGODB_PASSWORD', 'PINECONE_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print("Error: Required environment variables are missing.")
            print("Please make sure the following variables are defined in your .env file:")
            for var in required_vars:
                print(f"- {var}")
            print("- MONGODB_URI (optional, will be constructed if not provided)")
            print("- PINECONE_INDEX_NAME (optional)")
            print("- PINECONE_CLOUD (optional)")
            print("- PINECONE_REGION (optional)")
            print("- OPENAI_API_KEY (optional, for entity extraction)")
            sys.exit(1)
            
        args = parse_arguments()
        
        # Create configuration dictionary
        app_config = {
            "index_name": config["PINECONE_INDEX_NAME"],
            "cloud": config["PINECONE_CLOUD"],
            "region": config["PINECONE_REGION"],
            "batch_size": 10,
            "cursor_batch_size": 100  # Default cursor batch size
        }
        
        # Update config from command line arguments
        if args.index_name:
            app_config["index_name"] = args.index_name
            
        if args.cloud:
            app_config["cloud"] = args.cloud
            
        if args.region:
            app_config["region"] = args.region
            
        if args.batch_size:
            app_config["batch_size"] = args.batch_size
            
        if args.cursor_batch_size:
            app_config["cursor_batch_size"] = args.cursor_batch_size
            print(f"Using cursor batch size: {app_config['cursor_batch_size']}")
        
        # Get resume document ID if specified
        resume_id = args.resume_id
        if resume_id:
            print(f"Will resume processing from document ID: {resume_id}")
            
        print(f"Using Pinecone index: {app_config['index_name']}")
        print(f"Using Pinecone cloud: {app_config['cloud']}, region: {app_config['region']}")
        
        # Connect to MongoDB for listing or validation
        client = connect_to_mongodb()
        
        # Just list available collections if requested
        if args.list_only:
            list_available_collections(client)]
            sys.exit(0)
        
        # Initialize entity extraction agent if not explicitly skipped
        entity_agent = None
        if not args.skip_entity_extraction:
            entity_agent = initialize_entity_extraction_agent()
            if entity_agent:
                print("Entity extraction enabled - articles will be processed for named entities")
            else:
                print("Entity extraction disabled - OpenAI API key not found")
        else:
            print("Entity extraction disabled by command line argument")
        
        # Parse the collections argument if provided
        mongodb_collections = config["DEFAULT_MONGODB_COLLECTIONS"]
        if args.collections:
            mongodb_collections = []
            for coll_spec in args.collections:
                parts = coll_spec.split('.')
                if len(parts) != 2:
                    print(f"Error: Invalid collection format '{coll_spec}'. Use format 'db_name.collection_name'")
                    sys.exit(1)
                db_name, collection_name = parts
                mongodb_collections.append({"db": db_name, "collection": collection_name})
            
            # Validate that the specified collections exist
            for coll_config in mongodb_collections:
                db_name = coll_config["db"]
                collection_name = coll_config["collection"]
                
                if db_name not in client.list_database_names():
                    print(f"Warning: Database '{db_name}' does not exist.")
                    continue
                
                if collection_name not in client[db_name].list_collection_names():
                    print(f"Warning: Collection '{collection_name}' does not exist in database '{db_name}'.")
                    continue
        
        print(f"Processing the following collections:")
        for coll in mongodb_collections:
            print(f"  - {coll['db']}.{coll['collection']}")
        
        # Examine schema of first document in each collection to debug field names
        print("\nExamining database schemas:")
        for coll_config in mongodb_collections:
            db_name = coll_config["db"]
            collection_name = coll_config["collection"]
            db = client[db_name]
            collection = db[collection_name]
            
            sample_doc = collection.find_one()
            if sample_doc:
                print(f"\nSample document fields from {db_name}.{collection_name}:")
                for key in sample_doc.keys():
                    if key != "_id":
                        value = sample_doc[key]
                        value_preview = str(value)[:50] + "..." if isinstance(value, str) and len(str(value)) > 50 else value
                        print(f"  - {key}: {value_preview}")
        
        # Initialize Pinecone with the updated configuration
        index = initialize_pinecone(app_config["index_name"], app_config["cloud"], app_config["region"])
        
        # Process each collection
        total_processed = 0
        collection_results = []
        
        # Check if we should skip some collections (for resuming)
        resume_mode = False
        if args.resume_from:
            resume_mode = True
            resume_parts = args.resume_from.split('.')
            if len(resume_parts) != 2:
                print(f"Error: Invalid resume format '{args.resume_from}'. Use format 'db_name.collection_name'")
                sys.exit(1)
            resume_db, resume_collection = resume_parts
            print(f"Will resume processing from {resume_db}.{resume_collection}")
        
        for db_config in mongodb_collections:
            db_name = db_config["db"]
            collection_name = db_config["collection"]
            
            # Skip collections until we reach the resume point
            if resume_mode:
                if db_name != resume_db or collection_name != resume_collection:
                    print(f"Skipping {db_name}.{collection_name} (resume mode)")
                    continue
                else:
                    # Found the resume point, turn off resume mode so we process all subsequent collections
                    resume_mode = False
            
            start_time = time.time()
            processed = migrate_collection_to_pinecone(
                client, 
                db_name, 
                collection_name, 
                index,
                entity_agent,  # Pass the entity extraction agent
                app_config["batch_size"],
                resume_id
            )
            elapsed_time = time.time() - start_time
            
            total_processed += processed
            collection_results.append({
                "db": db_name,
                "collection": collection_name,
                "processed": processed,
                "time": elapsed_time
            })
            
            # Reset resume_id after first use
            resume_id = None
        
        # Print summary report
        print("\n" + "="*80)
        print("MIGRATION SUMMARY REPORT")
        print("="*80)
        print(f"{'Database':<20} {'Collection':<20} {'Documents':<10} {'Time (s)':<10}")
        print("-"*80)
        for result in collection_results:
            print(f"{result['db']:<20} {result['collection']:<20} {result['processed']:<10} {result['time']:.2f}")
        print("-"*80)
        print(f"Total documents processed: {total_processed}")
        print("="*80 + "\n")
        
        print(f"Overall migration complete! Processed {total_processed} documents in total.")
        
    except Exception as e:
        print(f"Script execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()