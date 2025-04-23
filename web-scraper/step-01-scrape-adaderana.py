import requests
from bs4 import BeautifulSoup
import re
import time
import json
from datetime import datetime
import argparse
import os
import sys

# Import modules from local files (same as in the first script)
from config import load_config
from embeddings.mongo_client import connect_to_mongodb
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def clean_text(text):
    """
    Cleans text by removing special characters and extra line breaks.
    
    Args:
        text (str): Text to clean
        
    Returns:
        str: Cleaned text
    """
    # Remove extra whitespace and line breaks
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s.,;:!?()-]', '', text)
    return text.strip()

def extract_news_data(url):
    """
    Extracts news data from the given URL.
    
    Args:
        url (str): URL to scrape
        
    Returns:
        dict: Dictionary containing the news data or error message
    """
    # Add a user agent to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Make the request to the website
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if the page exists (status code 200)
        if response.status_code != 200:
            return {
                "error": f"Page not found: Status code {response.status_code}",
                "url": url
            }
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the article tag with class="news"
        article_tag = soup.find('article', class_='news')
        
        if not article_tag:
            return {
                "error": "No <article class=\"news\"> tag found on the page.",
                "url": url
            }
        
        # Extract the requested data
        news_id = url.split("nid=")[1]
        results = {
            "url": url,
            "news_id": news_id,
            "title": "",
            "date": "",
            "content": ""
        }
        
        # Extract title text from h1 tag
        h1_tag = article_tag.find('h1')
        if h1_tag:
            results["title"] = clean_text(h1_tag.get_text())
        else:
            results["title"] = "No title found"
        
        # Extract date from p tag with class="news-datestamp"
        date_tag = article_tag.find('p', class_='news-datestamp')
        if date_tag:
            results["date"] = clean_text(date_tag.get_text())
        else:
            results["date"] = "No date found"
        
        # Extract content from div with class="news-content"
        content_tag = article_tag.find('div', class_='news-content')
        if content_tag:
            # Get all text from the content div
            all_text = content_tag.get_text()
            results["content"] = clean_text(all_text)
        else:
            results["content"] = "No content found"
        
        return results
        
    except requests.exceptions.RequestException as e:
        return {
            "error": f"Error fetching the URL: {e}",
            "url": url
        }
    except Exception as e:
        return {
            "error": f"An error occurred: {e}",
            "url": url
        }

def save_to_json(data, output_dir="adaderana_articles", filename=None, batch_num=None):
    """
    Saves the data to a JSON file in the specified directory.
    
    Args:
        data (list): List of data to save
        output_dir (str): Directory to save the file to
        filename (str, optional): Name of the file to save to. Defaults to None.
        batch_num (int, optional): Batch number to include in filename. Defaults to None.
        
    Returns:
        str: Full path of the file that was saved
    """
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
    
    if filename is None:
        # Generate a filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if batch_num is not None:
            filename = f"adaderana_news_batch{batch_num}_{timestamp}.json"
        else:
            filename = f"adaderana_news_{timestamp}.json"
    
    # Combine the directory and filename
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)
    
    return filepath

def save_progress(current_id, output_dir="adaderana_articles"):
    """
    Saves the current progress to a progress file.
    
    Args:
        current_id (int): The last processed news ID
        output_dir (str): Directory to save the progress file
    """
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    progress_file = os.path.join(output_dir, "scraping_progress.json")
    
    progress_data = {
        "last_processed_id": current_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, indent=4)

def save_to_mongodb(client, db_name, collection_name, article, batch_num=None):
    """
    Save a single article to MongoDB collection using the shared client approach.
    
    Args:
        client: MongoDB client connection
        db_name (str): Database name
        collection_name (str): Collection name
        article (dict): Article data to save
        batch_num (int, optional): Batch number to include in batch_id. Defaults to None.
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    if client is None or not article:
        print("No MongoDB client or article to save")
        return False
    
    try:
        # Get database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        # Add timestamp and batch information to the document
        timestamp = datetime.now().isoformat()
        batch_id = f"batch_{batch_num}" if batch_num is not None else f"batch_{timestamp}"
        
        # Create a deep copy of the article to avoid modifying the original
        article_copy = article.copy()
        article_copy['timestamp'] = timestamp
        article_copy['batch_id'] = batch_id
        # Add source field for easier identification in the migration process
        article_copy['source'] = 'adaderana.lk'
        
        # Insert article into MongoDB
        result = collection.insert_one(article_copy)
        if result.inserted_id:
            return True
        return False
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")
        return False

def load_progress(output_dir="adaderana_articles", default_start_id=87263):
    """
    Loads the last processed news ID from the progress file.
    
    Args:
        output_dir (str): Directory where the progress file is stored
        default_start_id (int): Default start ID if no progress file exists
        
    Returns:
        int: The last processed news ID
    """
    progress_file = os.path.join(output_dir, "scraping_progress.json")
    
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                return progress_data.get("last_processed_id", default_start_id)
        except Exception as e:
            print(f"Error loading progress file: {e}")
            return default_start_id
    else:
        return default_start_id

def create_mongodb_indexes(client, db_name, collection_name):
    """
    Create indexes for better query performance.
    
    Args:
        client: MongoDB client connection
        db_name (str): Database name
        collection_name (str): Collection name
    """
    try:
        # Get database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        # Create useful indexes
        collection.create_index([("url", 1)], unique=True)
        collection.create_index([("title", "text"), ("content", "text")])
        collection.create_index([("date", 1)])
        collection.create_index([("news_id", 1)])
        print("MongoDB indexes created successfully")
    except Exception as e:
        print(f"Error creating MongoDB indexes: {e}")

def parse_arguments():
    """Parse command line arguments for flexible scraping options"""
    config = load_config()
    
    parser = argparse.ArgumentParser(description='Scrape Ada Derana news articles in batches')
    parser.add_argument('--start', type=int, help='Starting news ID (default: last processed ID or 87263)')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of articles per batch (default: 100)')
    parser.add_argument('--batches', type=int, default=1, help='Number of batches to process (default: 1)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--output-dir', type=str, default='adaderana_articles', help='Output directory (default: adaderana_articles)')
    parser.add_argument('--resume', action='store_true', help='Resume from the last processed ID')
    parser.add_argument('--db-name', type=str, default="adaderana_data", 
                        help='MongoDB database name (default: adaderana_data)')
    parser.add_argument('--collection-name', type=str, default="articles", 
                        help='MongoDB collection name (default: articles)')
    parser.add_argument('--skip-mongodb', action='store_true', 
                        help='Skip saving to MongoDB (JSON only)')
    
    return parser.parse_args()

def main():
    # Load environment variables and configuration
    load_dotenv()
    config = load_config()
    
    # Parse command line arguments
    args = parse_arguments()
    
    print("Starting Ada Derana news scraper...")
    
    # Make sure environment variables are properly loaded if using MongoDB
    if not args.skip_mongodb:
        required_vars = ['MONGODB_USERNAME', 'MONGODB_PASSWORD']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print("Error: Required environment variables are missing.")
            print("Please make sure the following variables are defined in your .env file:")
            for var in required_vars:
                print(f"- {var}")
            print("Continuing with JSON output only.")
            args.skip_mongodb = True
    
    output_dir = args.output_dir
    batch_size = args.batch_size
    num_batches = args.batches
    delay = args.delay
    
    # Connect to MongoDB if not skipped
    mongo_client = None
    if not args.skip_mongodb:
        try:
            # Connect to MongoDB using the shared module
            mongo_client = connect_to_mongodb()
            if mongo_client is None:
                print("MongoDB connection failed. Continuing with JSON output only.")
                args.skip_mongodb = True
            else:
                print(f"Successfully connected to MongoDB. Will save articles to database: {args.db_name}, collection: {args.collection_name}")
                
                # Create indexes for better performance
                create_mongodb_indexes(mongo_client, args.db_name, args.collection_name)
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            print("Continuing with JSON output only.")
            args.skip_mongodb = True
    
    # Determine the starting ID
    if args.resume or args.start is None:
        start_id = load_progress(output_dir)
        print(f"Resuming from ID {start_id}")
    else:
        start_id = args.start
        print(f"Starting from ID {start_id}")
    
    base_url = "https://www.adaderana.lk/news.php?nid="
    
    total_articles = batch_size * num_batches
    print(f"Scraping {total_articles} news articles in {num_batches} batches of {batch_size} articles each")
    print("-" * 80)
    
    current_id = start_id
    
    for batch in range(num_batches):
        print(f"\nStarting Batch {batch+1}/{num_batches}")
        print(f"Processing IDs {current_id} to {current_id + batch_size - 1}")
        print("-" * 80)
        
        # List to store batch results
        batch_results = []
        
        # Counter for valid articles found in this batch
        valid_count = 0
        
        for i in range(batch_size):
            article_id = current_id + i
            url = f"{base_url}{article_id}"
            print(f"\nChecking URL {i+1}/{batch_size} in Batch {batch+1}: {url}")
            
            # Extract data from the URL
            results = extract_news_data(url)
            
            if "error" in results:
                print(f"Error: {results['error']}")
                # Add to results with error flag
                batch_results.append({
                    "news_id": article_id,
                    "url": url,
                    "valid": False,
                    "error": results["error"]
                })
                continue
            
            # Add success flag to results
            results["valid"] = True
            batch_results.append(results)
            
            # Save to MongoDB if connection is available and not skipped
            if not args.skip_mongodb and mongo_client is not None:
                if save_to_mongodb(mongo_client, args.db_name, args.collection_name, results, batch_num=batch+1):
                    print(f"Saved article ID {article_id} to MongoDB")
                else:
                    print(f"Failed to save article ID {article_id} to MongoDB")
            
            valid_count += 1
            print(f"\nNews Page URL: {results['url']}")
            print(f"News Title: {results['title']}")
            print(f"Date: {results['date']}")
            print(f"Page Content: {results['content'][:300]}...") # Showing first 300 chars to keep output manageable
            print("-" * 80)
            
            # Add a delay to avoid overloading the server
            if i < batch_size - 1:  # Don't sleep after the last request in batch
                time.sleep(delay)
        
        # Save batch results
        batch_num = batch + 1
        filepath = None
        
        # Save to JSON file (batch level)
        filepath = save_to_json(batch_results, output_dir, batch_num=batch_num)
        print(f"Batch results saved to JSON file: {filepath}")
        
        # Update current_id for next batch
        current_id += batch_size
        
        # Save progress after each batch
        save_progress(current_id, output_dir)
        
        print(f"\nBatch {batch_num} complete. Found {valid_count} valid articles out of {batch_size} attempts.")
        print(f"Progress saved. Next starting ID will be {current_id}")
        
        if batch < num_batches - 1:
            print(f"Waiting 5 seconds before starting next batch...")
            time.sleep(5)  # Add a longer delay between batches
    
    print(f"\nAll batches complete. Scraped {total_articles} articles in {num_batches} batches.")
    print(f"JSON batch results saved to {output_dir}")
    
    if not args.skip_mongodb and mongo_client is not None:
        print(f"Individual articles saved to MongoDB database: {args.db_name}, collection: {args.collection_name}")
    
    # Close MongoDB connection if open
    if mongo_client is not None:
        mongo_client.close()
        print("MongoDB connection closed")

if __name__ == "__main__":
    main()