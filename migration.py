import pymongo
from pymongo.errors import CursorNotFound
from bson.objectid import ObjectId
from tqdm import tqdm

from utils import vectorize_text, parse_date

def migrate_collection_to_pinecone(client, db_name, collection_name, index, entity_agent=None, batch_size=50, resume_id=None):
    """Migrate data from a specific MongoDB collection to Pinecone."""
    try:
        # Connect to the specific database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        # Count total documents for progress tracking
        total_docs = collection.count_documents({})
        print(f"Found {total_docs} documents in {db_name}.{collection_name}.")
        
        # Process documents in batches
        processed_count = 0
        batch_vectors = []
        skipped_count = 0
        
        # Use smaller cursor batch size to avoid timeouts
        cursor_batch_size = 100
        
        # Setup query filter for resuming if needed
        query_filter = {}
        if resume_id:
            try:
                resume_obj_id = ObjectId(resume_id)
                query_filter = {"_id": {"$gte": resume_obj_id}}
                print(f"Resuming from document ID: {resume_id}")
            except Exception as e:
                print(f"Warning: Could not parse resume_id as ObjectId: {e}")
                print("Will process all documents")
        
        # Use find with smaller cursor batch size and no_cursor_timeout=False (important)
        # Process in smaller batches with periodic cursor refresh
        for skip_count in range(0, total_docs, cursor_batch_size):
            # Create a new cursor for each batch to avoid cursor timeouts
            # Note: We're explicitly NOT using no_cursor_timeout=True here to prevent resource leaks
            cursor = collection.find(
                query_filter,
                batch_size=cursor_batch_size  # Smaller batch size
            ).skip(skip_count).limit(cursor_batch_size)
            
            # Process documents in this cursor batch
            current_batch_count = 0
            try:
                for doc in tqdm(cursor, total=min(cursor_batch_size, total_docs-skip_count), 
                             desc=f"Processing {db_name}.{collection_name} (batch {skip_count//cursor_batch_size + 1})"):
                    try:
                        # Extract necessary fields with better field detection
                        mongo_id = str(doc["_id"])
                        
                        # Try different possible field names for URL
                        url = doc.get("News Page URL", "")
                        if not url:
                            url = doc.get("url", "")
                            if not url:
                                url = doc.get("URL", "")
                        
                        # Try different possible field names for date
                        date = doc.get("Date", "")
                        if not date:
                            date = doc.get("date", "")
                            if not date:
                                date = doc.get("published_date", "")
                        
                        # Standardize the date format
                        standardized_date = parse_date(date)
                        
                        # Try different possible field names for title
                        title = doc.get("News Title", "")
                        if not title:
                            title = doc.get("title", "")
                            if not title:
                                title = doc.get("headline", "")
                        
                        # Try different possible field names for content
                        content = doc.get("Page Content", "")
                        if not content:
                            content = doc.get("content", "")
                            if not content:
                                content = doc.get("article_text", "")
                                if not content:
                                    content = doc.get("body", "")
                        
                        # Skip documents with no meaningful content
                        if not title and not content:
                            print(f"Skipping document {mongo_id} with no title or content")
                            skipped_count += 1
                            continue
                        
                        # Create combined text for vectorization
                        vectorization_text = f"{title} {content}"
                        if len(vectorization_text.strip()) < 10:  # Skip documents with minimal content
                            print(f"Skipping document {mongo_id} with insufficient content")
                            skipped_count += 1
                            continue
                        
                        # Print first document details to debug field mappings
                        if processed_count == 0:
                            print("\nFirst document field mapping:")
                            print(f"MongoDB ID: {mongo_id}")
                            print(f"URL: {url[:50]}...")
                            print(f"Original Date: {date}")
                            print(f"Standardized Date: {standardized_date}")
                            print(f"Title: {title[:50]}...")
                            print(f"Content length: {len(content)} chars")
                            print(f"Available fields in document: {list(doc.keys())}")
                            print("\n")
                        
                        # Generate vector embedding
                        vector = vectorize_text(vectorization_text)
                        
                        # Extract entities if agent is available
                        keywords = []
                        if entity_agent:
                            try:
                                keywords = entity_agent.process_article_entities(vectorization_text)
                                print(f"Keywords list: {keywords}")
                            except Exception as entity_err:
                                print(f"Error extracting entities for document {mongo_id}: {entity_err}")
                        
                        # Calculate how much space we need to reserve for other metadata fields
                        other_metadata_size = (
                            len(str(url)) + 
                            len(str(standardized_date)) + 
                            len(str(title)) + 
                            len(str(mongo_id)) + 
                            len(db_name) + 
                            len(str(keywords))  # Account for keywords
                        )
                        # Add some buffer for field names and JSON structure overhead (approx. 100 bytes)
                        other_metadata_size += 200  # Increased buffer for the additional fields
                        # Calculate maximum size for content (leave 1KB buffer to be safe)
                        max_content_size = 39000 - other_metadata_size  # 39KB instead of 40KB for safety buffer

                        # Truncate content if necessary
                        truncated_content = content
                        if len(content) > max_content_size:
                            truncated_content = content[:max_content_size] + "... [truncated]"
                            print(f"Truncated content for document {mongo_id} from {len(content)} to {len(truncated_content)} bytes")
                            print(url)
                        
                        # Create the metadata dictionary with the truncated content
                        metadata = {
                            "url": str(url),
                            "date": str(standardized_date),
                            "title": str(title),
                            "mongo_id": str(mongo_id),
                            "source_db": db_name,
                            "content": str(truncated_content),  # Use truncated content
                            "keywords": keywords  # Add flat list of keywords
                        }
                        
                        # Create a record for Pinecone
                        record = {
                            "id": f"{db_name}_{mongo_id}",  # Modified ID format to remove collection reference
                            "values": vector,
                            "metadata": metadata
                        }
                        
                        batch_vectors.append(record)
                        processed_count += 1
                        current_batch_count += 1
                        
                        # If batch is full, upsert to Pinecone
                        if len(batch_vectors) >= batch_size:
                            index.upsert(vectors=batch_vectors)
                            print(f"Uploaded batch of {len(batch_vectors)} vectors to Pinecone")
                            # Save the last processed ID for potential resuming
                            last_id = mongo_id
                            print(f"Last processed ID: {last_id}")
                            batch_vectors = []
                        
                        # Update resume_id for query filter if we're in the first batch
                        if skip_count == 0 and current_batch_count == cursor_batch_size - 1:
                            # Save the last ID of the first batch for potential issues
                            print(f"First batch complete, last ID: {mongo_id}")
                            
                    except Exception as e:
                        print(f"Error processing document {doc.get('_id')}: {e}")
                        continue
                
                # Make sure to close the cursor explicitly after processing this batch
                cursor.close()
                
            except CursorNotFound as e:
                print(f"Cursor timeout occurred, will create a new cursor. Error: {e}")
                # Save the last batch of vectors if any
                if batch_vectors:
                    try:
                        index.upsert(vectors=batch_vectors)
                        print(f"Uploaded batch of {len(batch_vectors)} vectors to Pinecone before cursor recreation")
                        batch_vectors = []
                    except Exception as upload_err:
                        print(f"Error uploading batch after cursor timeout: {upload_err}")
                continue
                
            except Exception as e:
                print(f"Error processing batch starting at {skip_count}: {e}")
                # Try to save any collected vectors before continuing
                if batch_vectors:
                    try:
                        index.upsert(vectors=batch_vectors)
                        print(f"Uploaded batch of {len(batch_vectors)} vectors to Pinecone after error")
                        batch_vectors = []
                    except Exception as upload_err:
                        print(f"Error uploading batch after error: {upload_err}")
                continue
                
        # Upload any remaining vectors
        if batch_vectors:
            index.upsert(vectors=batch_vectors)
            print(f"Uploaded final batch of {len(batch_vectors)} vectors to Pinecone")
        
        print(f"Migration of {db_name}.{collection_name} complete!")
        print(f"Processed: {processed_count} documents")
        print(f"Skipped: {skipped_count} documents")
        print(f"Total: {total_docs} documents")
        return processed_count
        
    except Exception as e:
        print(f"Migration of {db_name}.{collection_name} failed: {e}")
        return 0