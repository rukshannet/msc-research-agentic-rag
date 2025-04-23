import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import html
import unicodedata
import os
from datetime import datetime, timedelta
import time
import random
import argparse
import math
import sys

# Import modules from local files (same as in the first script)
from config import load_config
from embeddings.mongo_client import connect_to_mongodb
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def scrape_newswire_page(base_url, all_articles):
    print(f"\n{'='*50}")
    print(f"Scraping news from: {base_url}")
    print(f"{'='*50}")
    
    # Extract the date from the URL
    date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', base_url)
    if date_match:
        year, month, day = date_match.groups()
        page_date = f"{year}-{month}-{day}"
    else:
        page_date = "Unknown"
        print("Could not extract date from URL")
        return 0
    
    # Initialize tracking for all articles across all pages
    total_articles_found = 0
    current_page = 1
    has_next_page = True
    
    # Continue scraping while there are more pages
    while has_next_page:
        # Create the URL for the current page
        if current_page == 1:
            url = base_url
        else:
            url = f"{base_url}page/{current_page}/"
        
        print(f"Scraping page {current_page}: {url}")
        
        # Send HTTP request to the URL
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            # Use binary response and decode manually
            response = requests.get(url, headers=headers)
            
            # If we get a 404 for pages beyond the first, it means we've reached the end
            if response.status_code == 404 and current_page > 1:
                print(f"Page {current_page} not found (404). Reached the end of pagination.")
                break
                
            # Check if the request was successful
            if response.status_code != 200:
                print(f"Failed to retrieve page: Status code {response.status_code}")
                if current_page == 1:
                    return 0
                else:
                    break
            
            # Force trying different encodings
            content = try_encodings(response.content)
            
            # Parse the HTML content with correct encoding
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find all news articles on the page
            articles_found_on_page = 0
            
            # Look for article containers
            article_elements = soup.select('article.post')
            
            print(f"Found {len(article_elements)} articles on page {current_page}")
            
            if len(article_elements) == 0 and current_page == 1:
                print("No articles found on this date. The page might not exist or has a different structure.")
                return 0
            
            for article in article_elements:
                # Extract article title
                title_element = article.select_one('h2.entry-title a')
                if not title_element:
                    continue
                    
                title = clean_text(title_element.text.strip())
                
                # Extract article URL
                article_url = title_element['href']
                
                # Scrape the full article content
                article_content = scrape_article_content(article_url)
                
                # Add to our list
                all_articles.append({
                    'News Page URL': article_url,
                    'Date': page_date,
                    'News Title': title,
                    'Page Content': article_content
                })
                articles_found_on_page += 1
            
            total_articles_found += articles_found_on_page
            
            # Check if there's a next page
            next_page = soup.select_one('a.next.page-numbers')
            if not next_page:
                has_next_page = False
                print(f"No more pages found for {page_date}")
            else:
                current_page += 1
                # Add a delay before fetching the next page
                delay = random.uniform(1, 3)
                print(f"Found next page. Waiting {delay:.1f} seconds before continuing...")
                time.sleep(delay)
                
        except Exception as e:
            print(f"Error scraping page {current_page}: {str(e)}")
            if current_page == 1:
                return 0
            else:
                # If we encounter an error after the first page, we'll stop but count what we've already found
                break
    
    print(f"Completed scraping for {page_date} - Found {total_articles_found} articles across {current_page} pages")
    return total_articles_found

def try_encodings(content):
    """Try multiple encodings to decode the content correctly"""
    encodings = ['utf-8', 'iso-8859-1', 'windows-1252', 'ascii']
    
    for encoding in encodings:
        try:
            decoded = content.decode(encoding, errors='replace')
            # If we got here without an exception, use this encoding
            return decoded
        except UnicodeDecodeError:
            continue
    
    # If all failed, use replacement characters
    return content.decode('utf-8', errors='replace')

def scrape_article_content(article_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Add a random delay to be respectful to the server
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(article_url, headers=headers)
        
        if response.status_code != 200:
            return "Failed to retrieve article content"
        
        # Use the same encoding detection approach
        content = try_encodings(response.content)
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find the content div
        content_element = soup.select_one('div.entry-content')
        if not content_element:
            return "Content not found"
        
        # Convert to markdown
        markdown_content = html_to_markdown(content_element)
        
        return markdown_content
    except Exception as e:
        return f"Error retrieving content: {str(e)}"

def clean_text(text):
    """Apply multiple cleaning methods to fix character encoding issues"""
    # First unescape any HTML entities
    text = html.unescape(text)
    
    # Normalize Unicode (NFKC combines compatibility characters)
    text = unicodedata.normalize('NFKC', text)
    
    # Replace problematic characters
    replacements = {
        '\u2018': "'",  # Left single quotation mark
        '\u2019': "'",  # Right single quotation mark
        '\u201c': '"',  # Left double quotation mark
        '\u201d': '"',  # Right double quotation mark
        '\u2013': '-',  # En dash
        '\u2014': '--', # Em dash
        '\u2026': '...', # Ellipsis
        '\u00a0': ' ',  # Non-breaking space
        # Add these problematic UTF-8 sequences
        'â€™': "'",
        'â€œ': '"',
        'â€': '"',
        'â€"': '-',
        'â€¦': '...'
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text

def html_to_markdown(content_element):
    """Convert HTML content to simplified markdown format"""
    markdown = ""
    
    # Process paragraphs
    for p in content_element.find_all('p'):
        text = p.get_text().strip()
        if text:
            text = clean_text(text)
            markdown += text + "\n\n"
    
    # Process headings
    for i in range(1, 7):
        for h in content_element.find_all(f'h{i}'):
            text = h.get_text().strip()
            if text:
                text = clean_text(text)
                markdown += '#' * i + ' ' + text + "\n\n"
    
    # Process lists
    for ul in content_element.find_all('ul'):
        for li in ul.find_all('li'):
            text = li.get_text().strip()
            if text:
                text = clean_text(text)
                markdown += "* " + text + "\n"
        markdown += "\n"
    
    for ol in content_element.find_all('ol'):
        for i, li in enumerate(ol.find_all('li'), 1):
            text = li.get_text().strip()
            if text:
                text = clean_text(text)
                markdown += f"{i}. " + text + "\n"
        markdown += "\n"
    
    return markdown.strip()

def save_to_mongodb(client, db_name, collection_name, articles, week_start, week_end):
    """Save articles to MongoDB collection using the shared client module approach"""
    if client is None or not articles:
        print("No MongoDB client or articles to save")
        return 0
    
    try:
        # Get database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        # Add timestamp and batch information to each document
        timestamp = datetime.now().isoformat()
        batch_id = f"batch_{week_start}_to_{week_end}"
        
        # Create a deep copy of articles to avoid modifying the original list
        articles_to_insert = []
        for article in articles:
            article_copy = article.copy()  # Create a copy to avoid modifying original
            article_copy['timestamp'] = timestamp
            article_copy['batch_id'] = batch_id
            # Add a source field for easier identification in the migration process
            article_copy['source'] = 'newswire.lk'
            articles_to_insert.append(article_copy)
        
        # Insert articles into MongoDB
        result = collection.insert_many(articles_to_insert)
        inserted_count = len(result.inserted_ids)
        print(f"Successfully inserted {inserted_count} articles into MongoDB ({db_name}.{collection_name})")
        return inserted_count
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")
        return 0

def save_to_csv(all_articles, output_folder, date_range):
    """Save all the scraped articles to a single CSV file"""
    if not all_articles:
        print("No articles to save")
        return None
    
    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output folder: {output_folder}")
    
    # Create filename with date range
    start_date, end_date = date_range
    output_file = os.path.join(output_folder, f"newswire_articles_{start_date}_to_{end_date}.csv")
    
    df = pd.DataFrame(all_articles)
    
    # Clean all text fields again before saving
    for column in ['News Title', 'Page Content']:
        if column in df.columns:
            df[column] = df[column].apply(clean_text)
    
    # Save with UTF-8 encoding and BOM to help Excel open it correctly
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"Saved {len(all_articles)} articles to {output_file}")
    
    return output_file

def generate_weekly_batches(start_date_str, end_date_str=None, num_days=None):
    """
    Generate a list of weekly date batches from the start date
    Each batch contains 7 days or less (if it's the final batch)
    Returns a list of tuples, each containing (start_date, end_date) for a week
    """
    # Parse the start date
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    
    # Calculate end date
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    elif num_days:
        end_date = start_date + timedelta(days=num_days - 1)  # -1 because we include the start date
    else:
        # Default to 30 days if neither end_date nor num_days provided
        end_date = start_date + timedelta(days=29)  # 30 days including start date
    
    # Calculate total days
    total_days = (end_date - start_date).days + 1  # +1 to include both start and end dates
    
    # Calculate number of weeks (rounded up)
    num_weeks = math.ceil(total_days / 7)
    
    # Generate weekly batches
    weekly_batches = []
    for week in range(num_weeks):
        week_start = start_date + timedelta(days=week * 7)
        week_end = min(week_start + timedelta(days=6), end_date)  # Ensure we don't go past the overall end date
        
        weekly_batches.append((
            week_start.strftime('%Y-%m-%d'),
            week_end.strftime('%Y-%m-%d')
        ))
    
    return weekly_batches

def generate_dates_for_week(start_date_str, end_date_str):
    """Generate a list of dates for a specific week"""
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    
    return dates

def parse_arguments():
    """Parse command line arguments for flexible scraping options"""
    config = load_config()
    
    parser = argparse.ArgumentParser(description='Scrape articles from newswire.lk for a specified date range, saving weekly results')
    
    parser.add_argument('--start-date', type=str, default="2023-02-02",
                        help='Starting date in YYYY-MM-DD format (default: 2023-02-02)')
    
    # Make the end date and num_days mutually exclusive
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument('--end-date', type=str,
                        help='End date in YYYY-MM-DD format (inclusive)')
    date_group.add_argument('--num-days', type=int,
                        help='Number of days to scrape starting from start date')
    
    parser.add_argument('--output-folder', type=str, default="newswire_articles",
                        help='Folder to save the scraped articles (default: newswire_articles)')
    
    parser.add_argument('--delay-min', type=float, default=1.0,
                        help='Minimum delay between requests in seconds (default: 1.0)')
    
    parser.add_argument('--delay-max', type=float, default=3.0,
                        help='Maximum delay between requests in seconds (default: 3.0)')
    
    parser.add_argument('--page-delay-min', type=float, default=2.0,
                        help='Minimum delay between date pages in seconds (default: 2.0)')
    
    parser.add_argument('--page-delay-max', type=float, default=5.0,
                        help='Maximum delay between date pages in seconds (default: 5.0)')
    
    parser.add_argument('--skip-mongodb', action='store_true',
                        help='Skip saving to MongoDB (CSV only)')
    
    parser.add_argument('--db-name', type=str, default="newswire_data",
                        help=f'MongoDB database name (default: newswire_data)')
                        
    parser.add_argument('--collection-name', type=str, default="articles",
                        help=f'MongoDB collection name (default: articles)')
    
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Load configuration
    config = load_config()
    
    print("Starting Newswire.lk scraper...")
    
    # Set up delay parameters
    request_delay = (args.delay_min, args.delay_max)
    page_delay = (args.page_delay_min, args.page_delay_max)
    
    # Connect to MongoDB if not skipped
    mongo_client = None
    if not args.skip_mongodb:
        try:
            # Make sure environment variables are properly loaded
            required_vars = ['MONGODB_USERNAME', 'MONGODB_PASSWORD']
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if missing_vars:
                print("Error: Required environment variables are missing.")
                print("Please make sure the following variables are defined in your .env file:")
                for var in required_vars:
                    print(f"- {var}")
                sys.exit(1)
                
            # Connect to MongoDB using the shared module
            mongo_client = connect_to_mongodb()
            if mongo_client is None:
                print("MongoDB connection failed. Continuing with CSV output only.")
                args.skip_mongodb = True
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            print("Continuing with CSV output only.")
            args.skip_mongodb = True
    
    # Generate weekly batches of dates
    weekly_batches = generate_weekly_batches(args.start_date, args.end_date, args.num_days)
    
    # Display info about the scrape
    print(f"Starting scrape from {args.start_date}")
    if args.end_date:
        print(f"End date: {args.end_date}")
    elif args.num_days:
        print(f"Number of days: {args.num_days}")
    else:
        print("Default: 30 days")
        
    print(f"Total weeks to process: {len(weekly_batches)}")
    
    # Summary statistics
    total_articles = 0
    total_days_processed = 0
    total_days_with_articles = 0
    all_output_files = []
    total_mongodb_inserted = 0
    
    # Process each week
    for week_idx, (week_start, week_end) in enumerate(weekly_batches):
        print(f"\n{'#'*80}")
        print(f"Processing Week {week_idx+1}: {week_start} to {week_end}")
        print(f"{'#'*80}")
        
        # Generate dates for this week
        week_dates = generate_dates_for_week(week_start, week_end)
        
        # Create a list to hold articles for this week
        week_articles = []
        
        # Weekly statistics
        week_days_processed = 0
        week_days_with_articles = 0
        week_total_articles = 0
        
        # Process each date in the week
        for date_str in week_dates:
            # Convert date format from YYYY-MM-DD to YYYY/MM/DD for URL
            year, month, day = date_str.split('-')
            url = f"https://www.newswire.lk/{year}/{month}/{day}/"
            
            # Scrape the page for this date and add to our list
            articles_found = scrape_newswire_page(url, week_articles)
            
            # Update statistics
            week_days_processed += 1
            total_days_processed += 1
            if articles_found > 0:
                week_days_with_articles += 1
                total_days_with_articles += 1
                week_total_articles += articles_found
                total_articles += articles_found
            
            # Add a delay between requests to be respectful to the server
            if date_str != week_dates[-1]:  # Don't sleep after the last request of the week
                delay = random.uniform(page_delay[0], page_delay[1])
                print(f"Waiting {delay:.1f} seconds before next date...")
                time.sleep(delay)
        
        # Save this week's articles to MongoDB
        inserted_count = 0
        if len(week_articles) > 0 and not args.skip_mongodb and mongo_client is not None:
            inserted_count = save_to_mongodb(
                mongo_client, 
                args.db_name, 
                args.collection_name, 
                week_articles, 
                week_start, 
                week_end
            )
            total_mongodb_inserted += inserted_count
        
        # Save this week's articles to a CSV file
        if week_articles:
            output_file = save_to_csv(week_articles, args.output_folder, (week_start, week_end))
            if output_file:
                all_output_files.append(output_file)
        
        # Print weekly summary
        print(f"\n{'+'*60}")
        print(f"WEEK {week_idx+1} COMPLETE - SUMMARY")
        print(f"{'+'*60}")
        print(f"Date Range: {week_start} to {week_end}")
        print(f"Days Processed: {week_days_processed}/{len(week_dates)}")
        print(f"Days With Articles: {week_days_with_articles}")
        print(f"Articles Scraped This Week: {week_total_articles}")
        if not args.skip_mongodb and mongo_client is not None:
            print(f"Articles Saved to MongoDB This Week: {inserted_count}")
        print(f"{'+'*60}")
    
    # Close MongoDB connection
    if mongo_client is not None:
        mongo_client.close()
    
    # Print final summary
    print("\n" + "="*50)
    print("COMPLETE SCRAPING SUMMARY")
    print("="*50)
    print(f"Overall Date Range: {weekly_batches[0][0]} to {weekly_batches[-1][1]}")
    print(f"Total Days Processed: {total_days_processed}")
    print(f"Total Days With Articles: {total_days_with_articles}")
    print(f"Total Articles Scraped: {total_articles}")
    if not args.skip_mongodb:
        print(f"Total Articles Saved to MongoDB: {total_mongodb_inserted}")
    print(f"Output Files:")
    for file in all_output_files:
        print(f"  - {file}")
    print("="*50)

if __name__ == "__main__":
    main()
    