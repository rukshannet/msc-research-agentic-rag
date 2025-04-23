import requests
from bs4 import BeautifulSoup
import re
import time
import json
import random
from datetime import datetime, timedelta
import os
import argparse
import sys
from json import JSONEncoder
from bson import ObjectId

# Import modules from local files (same as in the first script)
from config import load_config
from embeddings.mongo_client import connect_to_mongodb
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def clean_text(text):
    """Clean text by removing extra whitespace and newlines."""
    if not text:
        return ""
    # Replace multiple spaces and newlines with a single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clean_content(content):
    """
    Clean article content by:
    1. Removing specific prefixes like "Colombo (News 1st) -"
    2. Removing special characters
    3. Normalizing whitespace
    """
    if not content:
        return ""
    
    content = content.strip()

    # Create a comprehensive list of exact prefixes to check (without regex)
    exact_prefixes = [
        "(BBC) - ",
        "Colombo (News 1st) - ",
        "Colombo (News 1st) -",
        "Colombo (News 1st);",
        "Colombo (News 1st):",
        "COLOMBO (News 1st): ",
        "COLOMBO (News 1st) - ",
        "COLOMBO (News 1st) -",
        "COLOMBO (News 1st);",
        "COLOMBO (News 1st):",
        "COLOMBO News 1st;",
        " COLOMBO News 1st;",
        " COLOMBO (News 1st):",
        "(Bloomberg) -- ",
        "Colombo (Sri Lanka) - ",
        "NEW DELHI (AP) - ",
        "TOKYO (AP) - ",
        "WASHINGTON (AP) - ",
        "LONDON (AP) - "
    ]
    
    # Check for each exact prefix
    for prefix in exact_prefixes:
        if content.startswith(prefix):
            content = content[len(prefix):]
            break  # Only remove one prefix
    
    # Also try with regex for any remaining variations
    regex_prefixes = [
        r'^\([A-Za-z]+\)\s*-\s*',
        r'^[A-Za-z]+\s*\([A-Za-z\s]+\s*[0-9]*[a-z]*\)\s*[-:;]\s*',
        r'^[A-Za-z]+\s*\([A-Za-z\s]+\)\s*[-:;]\s*'
    ]
    
    for prefix in regex_prefixes:
        content = re.sub(prefix, '', content, flags=re.IGNORECASE)
    
    # Remove special characters (keep basic punctuation)
    content = re.sub(r'[^\w\s.,;:?!\'"-]', ' ', content)
    
    # Replace newlines with spaces
    content = re.sub(r'\n+', ' ', content)
    
    # Replace tabs with spaces
    content = re.sub(r'\t+', ' ', content)
    
    # Remove multiple spaces
    content = re.sub(r'\s+', ' ', content)
    
    # Remove spaces before punctuation
    content = re.sub(r'\s+([.,;:?!])', r'\1', content)
    
    return content.strip()

def save_to_mongodb(client, db_name, collection_name, article_data):
    """
    Save article data to MongoDB using the shared client.
    
    Args:
        client: MongoDB client connection
        db_name (str): Database name
        collection_name (str): Collection name
        article_data (dict): Dictionary containing article data
        
    Returns:
        str: MongoDB document ID or error message
    """
    try:
        # Get database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        # Add timestamp for when record was added to database
        article_data['added_at'] = datetime.now()
        
        # Add source field for easier identification in the migration process
        article_data['source'] = 'newsfirst.lk'
        
        # Check if article with same URL already exists
        existing_article = collection.find_one({"url": article_data["url"]})
        
        if existing_article:
            # Update the existing article
            result = collection.update_one(
                {"_id": existing_article["_id"]},
                {"$set": article_data}
            )
            return f"Updated existing article with ID: {existing_article['_id']}"
        else:
            # Insert new article
            result = collection.insert_one(article_data)
            return f"Inserted new article with ID: {result.inserted_id}"
    
    except Exception as e:
        return f"Error saving to MongoDB: {e}"

def get_article_links(url):
    """
    Extracts all news article links from the main page.
    
    Args:
        url (str): URL of the main NewsFirst page
        
    Returns:
        list: List of article URLs
    """
    # Add a user agent to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Make the request to the website
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if the page exists
        if response.status_code != 200:
            print(f"Error: Page not found. Status code {response.status_code}")
            return []
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Initialize a list to store all article links
        article_links = []
        base_url = '/'.join(url.split('/')[:3])  # Get base URL (e.g., https://english.newsfirst.lk)
        
        # APPROACH 1: Original method - find standalone local_news_main div
        original_containers = soup.find_all('div', class_='local_news_main')
        if original_containers:
            print(f"Found {len(original_containers)} 'local_news_main' containers with original method")
            for container in original_containers:
                links = container.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    # Make relative URLs absolute
                    if href.startswith('/'):
                        href = base_url + href
                    article_links.append(href)
        
        # APPROACH 2: New method - find local_news_main divs inside lap_news_div
        lap_news_divs = soup.find_all('div', class_='lap_news_div')
        if lap_news_divs:
            print(f"Found {len(lap_news_divs)} 'lap_news_div' containers")
            for lap_div in lap_news_divs:
                # Find all local_news_main divs within each lap_news_div
                news_containers = lap_div.find_all('div', class_='local_news_main')
                
                if news_containers:
                    print(f"Found {len(news_containers)} 'local_news_main' containers within 'lap_news_div'")
                    
                    # Process each local_news_main container
                    for container in news_containers:
                        # Find all 'a' tags that link to articles
                        links = container.find_all('a', href=True)
                        
                        for link in links:
                            href = link['href']
                            # Make relative URLs absolute
                            if href.startswith('/'):
                                href = base_url + href
                            article_links.append(href)
        
        # If we still haven't found any links, look for other potential containers
        if not article_links:
            print("No article links found in standard containers, attempting to find articles in other elements...")
            
            # Look for common article container patterns
            potential_containers = soup.find_all(['div', 'section'], class_=lambda c: c and ('article' in c.lower() or 'news' in c.lower() or 'stories' in c.lower()))
            
            for container in potential_containers:
                links = container.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    # Make relative URLs absolute
                    if href.startswith('/'):
                        href = base_url + href
                    article_links.append(href)
        
        # Remove duplicates while preserving order
        unique_links = []
        for link in article_links:
            if link not in unique_links:
                unique_links.append(link)
        
        print(f"Found {len(unique_links)} unique article links for {url}")
        return unique_links
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return []
    except Exception as e:
        print(f"An error occurred with URL {url}: {e}")
        return []

def extract_article_data(article_url):
    """
    Extracts article data from the given article URL.
    
    Args:
        article_url (str): URL of the article page
        
    Returns:
        dict: Dictionary containing the article data
    """
    # Add a user agent to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Make the request to the website
        response = requests.get(article_url, headers=headers, timeout=10)
        
        # Check if the page exists
        if response.status_code != 200:
            return {
                "url": article_url,
                "error": f"Page not found: Status code {response.status_code}"
            }
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the main div
        main_div = soup.find('div', class_='main_div')
        
        if not main_div:
            return {
                "url": article_url,
                "error": "Could not find the 'main_div' container."
            }
        
        # Initialize result dictionary
        article_data = {
            "url": article_url,
            "title": "",
            "date": "",
            "content": ""
        }
        
        # Extract title
        title_element = main_div.find('h1', class_='top_stories_header_news')
        if title_element:
            article_data["title"] = clean_text(title_element.get_text())
        
        # Extract date
        date_element = main_div.find('span')
        if date_element:
            article_data["date"] = clean_text(date_element.get_text())
        
        # Extract content
        content_div = main_div.find('div', class_='new_details')
        if content_div:
            # Get all paragraphs
            paragraphs = content_div.find_all('p')
            # Join paragraphs with spaces (not newlines)
            content = " ".join([p.get_text() for p in paragraphs])
            # Clean the content
            article_data["content"] = clean_content(content)
        
        return article_data
    
    except requests.exceptions.RequestException as e:
        return {
            "url": article_url,
            "error": f"Error fetching the URL: {e}"
        }
    except Exception as e:
        return {
            "url": article_url,
            "error": f"An error occurred: {e}"
        }

def extract_all_news_articles(main_url, mongo_client, db_name, collection_name):
    """
    Extracts data from all news articles on the given page.
    
    Args:
        main_url (str): URL of the main NewsFirst page
        mongo_client: MongoDB client connection
        db_name (str): Database name
        collection_name (str): Collection name
        
    Returns:
        list: List of articles extracted
    """
    # Get all article links
    article_links = get_article_links(main_url)
    
    if not article_links:
        print(f"No article links found for {main_url}")
        return []
    
    # Extract data from each article
    articles_data = []
    
    # Process all unique article links found
    total_links = len(article_links)
    print(f"Preparing to process all {total_links} unique article links found")
    
    for i, link in enumerate(article_links, 1):
        # Skip non-article URLs (like pagination, category links, etc.)
        # Look for patterns that indicate an actual article
        if not (link.endswith('.html') or '/20' in link or any(term in link.lower() for term in ['article', 'news', 'story'])):
            print(f"Skipping likely non-article link: {link}")
            continue
            
        print(f"Processing article {i}/{total_links}: {link}")
        
        try:
            # Extract article data
            article_data = extract_article_data(link)
            
            # Check if we got actual content - skip empty articles
            if article_data.get('content') or article_data.get('title'):
                # Add source URL for reference
                article_data['source_page'] = main_url
                
                # Add to our collection
                articles_data.append(article_data)
                
                # Save to MongoDB immediately
                mongo_result = save_to_mongodb(mongo_client, db_name, collection_name, article_data)
                print(f"MongoDB: {mongo_result}")
            else:
                print(f"Skipping article with no content or title: {link}")
                
            # Sleep a bit to avoid overloading the server
            time.sleep(1)
            
        except Exception as e:
            print(f"Error processing article {link}: {e}")
            # Continue with the next article instead of breaking
            continue
    
    print(f"Successfully processed {len(articles_data)} out of {total_links} links for {main_url}")
    return articles_data

def generate_daily_date_sequence(start_date_str, end_date_str=None):
    """
    Generate a sequence of dates from start_date to end_date or today,
    with an interval of 1 day (daily).
    
    Args:
        start_date_str (str): Start date in YYYY/MM/DD format
        end_date_str (str, optional): End date in YYYY/MM/DD format, defaults to today
        
    Returns:
        list: List of date strings in YYYY/MM/DD format
    """
    # Parse the start date
    start_date = datetime.strptime(start_date_str, "%Y/%m/%d")
    
    # Parse the end date (default to today)
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y/%m/%d")
    else:
        end_date = datetime.now()
    
    # Calculate the range of days between start and end
    date_range = (end_date - start_date).days
    
    if date_range < 0:
        print("Warning: Start date is after end date. Using today as end date.")
        end_date = datetime.now()
        date_range = (end_date - start_date).days
    
    # Generate sequence of dates (daily)
    date_sequence = []
    current_date = start_date
    
    while current_date <= end_date:
        date_sequence.append(current_date.strftime("%Y/%m/%d"))
        current_date += timedelta(days=1)  # Increment by 1 day for daily scraping
    
    return date_sequence

def get_processed_urls_from_db(client, db_name, collection_name):
    """
    Retrieves all source_page URLs that have already been processed
    
    Args:
        client: MongoDB client connection
        db_name (str): Database name
        collection_name (str): Collection name
        
    Returns:
        set: Set of URLs already processed
    """
    try:
        # Get database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        # Get distinct source_page values
        processed_urls = collection.distinct("source_page")
        return set(processed_urls)
    except Exception as e:
        print(f"Error retrieving processed URLs from database: {e}")
        return set()

# Custom JSON Encoder to handle datetime objects and MongoDB ObjectId
class DateTimeEncoder(JSONEncoder):
    """Custom JSON encoder for handling datetime and ObjectId objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return JSONEncoder.default(self, obj)

def create_mongodb_indexes(client, db_name, collection_name):
    """
    Create indexes for better query performance
    
    Args:
        client: MongoDB client connection
        db_name (str): Database name
        collection_name (str): Collection name
    """
    try:
        # Get database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        collection.create_index([("url", 1)], unique=True)
        collection.create_index([("title", "text"), ("content", "text")])
        collection.create_index([("date", 1)])
        collection.create_index([("source_page", 1)])
        print("MongoDB indexes created")
    except Exception as e:
        print(f"Error creating MongoDB indexes: {e}")

def parse_arguments():
    """Parse command line arguments for flexible scraping options"""
    config = load_config()
    
    parser = argparse.ArgumentParser(description='Scrape NewsFirst articles')
    
    base_url = "https://english.newsfirst.lk/"
    start_date = "2023/01/01"
    end_date = datetime.now().strftime("%Y/%m/%d")
    
    parser.add_argument('--startdate', default=start_date, help=f'Start date in YYYY/MM/DD format (default: {start_date})')
    parser.add_argument('--enddate', default=end_date, help=f'End date in YYYY/MM/DD format (default: today, {end_date})')
    parser.add_argument('--output', default="newsfirst_articles_full.json", help='Output JSON filename')
    parser.add_argument('--skip-file', action='store_true', help='Skip saving to JSON file (use MongoDB only)')
    parser.add_argument('--skip-processed', action='store_true', help='Skip URLs already processed in the database')
    parser.add_argument('--specific-date', help='Scrape a single specific date in YYYY/MM/DD format')
    
    parser.add_argument('--db-name', type=str, default="newsfirst_data",
                        help=f'MongoDB database name (default: newsfirst_data)')
                        
    parser.add_argument('--collection-name', type=str, default="articles",
                        help=f'MongoDB collection name (default: articles)')
    
    # Note: We've removed the interval parameter as it's no longer needed
    
    return parser.parse_args()

def main():
    # Load environment variables and configuration
    load_dotenv()
    config = load_config()
    
    # Parse command line arguments
    args = parse_arguments()
    
    print("Starting NewsFirst.lk scraper...")
    
    # Make sure environment variables are properly loaded
    required_vars = ['MONGODB_USERNAME', 'MONGODB_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("Error: Required environment variables are missing.")
        print("Please make sure the following variables are defined in your .env file:")
        for var in required_vars:
            print(f"- {var}")
        sys.exit(1)
    
    try:
        # Connect to MongoDB
        mongo_client = connect_to_mongodb()
        if mongo_client is None:
            print("MongoDB connection failed. Exiting.")
            sys.exit(1)
            
        # Ensure MongoDB indexes are created
        create_mongodb_indexes(mongo_client, args.db_name, args.collection_name)
        
        # Create output directory if it doesn't exist and file output is enabled
        output_dir = "newsfirst_articles"
        if not args.skip_file and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        
        # Get already processed URLs if requested
        processed_urls = set()
        if args.skip_processed:
            processed_urls = get_processed_urls_from_db(mongo_client, args.db_name, args.collection_name)
            print(f"Found {len(processed_urls)} already processed URLs")
        
        # Create a flat list to store all articles
        all_articles = []
        
        # Define base URL for NewsFirst
        base_url = "https://english.newsfirst.lk/"
        
        # Process either a specific date or a date range
        if args.specific_date:
            # Process a single specific date
            url = f"{base_url}{args.specific_date}"
            print(f"\nProcessing single URL: {url}")
            
            # Extract news data as a flat list
            articles = extract_all_news_articles(url, mongo_client, args.db_name, args.collection_name)
            all_articles.extend(articles)
        else:
            # Generate sequence of dates (daily)
            date_sequence = generate_daily_date_sequence(args.startdate, args.enddate)
            total_dates = len(date_sequence)
            print(f"Generated sequence of {total_dates} daily dates from {date_sequence[0]} to {date_sequence[-1]}")
            
            # Process each date in the sequence
            for date_index, date in enumerate(date_sequence, 1):
                # Format URL with date
                url = f"{base_url}{date}"
                
                # Skip if already processed
                if url in processed_urls:
                    print(f"\nSkipping already processed URL {date_index}/{total_dates}: {url}")
                    continue
                
                print(f"\nProcessing URL {date_index}/{total_dates}: {url}")
                
                # Extract news data as a flat list
                articles = extract_all_news_articles(url, mongo_client, args.db_name, args.collection_name)
                
                # Add to our collection
                all_articles.extend(articles)
                
                # Save ongoing progress to temporary file if file output is enabled
                if not args.skip_file:
                    temp_file = os.path.join(output_dir, "temp_progress.json")
                    with open(temp_file, "w", encoding="utf-8") as f:
                        json.dump(all_articles, f, ensure_ascii=False, indent=4, cls=DateTimeEncoder)
                    print(f"Saved current progress to temporary file")
                
                # Sleep between dates to avoid overloading the server
                if date_index < total_dates:  # Don't sleep after the last date
                    sleep_time = 2  # Reduced sleep time since we're processing daily
                    print(f"Sleeping for {sleep_time} seconds before next date...")
                    time.sleep(sleep_time)
        
        # Save to a JSON file in the newsfirst_articles folder if file output is enabled
        if not args.skip_file:
            output_file = os.path.join(output_dir, args.output)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_articles, f, ensure_ascii=False, indent=4, cls=DateTimeEncoder)
            
            # Remove temporary file if it exists
            temp_file = os.path.join(output_dir, "temp_progress.json")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            print(f"Data saved to {output_file}")
        
        # Print summary
        print("\n=== SUMMARY ===")
        if args.specific_date:
            print(f"Processed specific date: {args.specific_date}")
            print(f"Total articles extracted: {len(all_articles)}")
        else:
            print(f"Processed daily date range from {args.startdate} to {args.enddate}")
            print(f"Total articles extracted: {len(all_articles)}")
        print(f"All articles have been saved to MongoDB database: {args.db_name}, collection: {args.collection_name}")
        
        # Close MongoDB connection
        mongo_client.close()
        
    except Exception as e:
        print(f"Script execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()