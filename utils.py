import re
from datetime import datetime
from sentence_transformers import SentenceTransformer

# Initialize sentence transformer model for vectorization
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')

def parse_date(date_str):
    """
    Parse different date formats and return a standardized ISO format (YYYY-MM-DD).
    """
    if not date_str:
        return ""
        
    try:
        # Handle Newsfirst format: "08-01-2023 | 7:46 PM"
        if '|' in date_str:
            date_part = date_str.split('|')[0].strip()
            try:
                dt = datetime.strptime(date_part, "%d-%m-%Y")
                return dt.strftime("%Y-%m-%d")
            except:
                pass
        
        # Handle Adaderana format: "January 1, 2023 08:07 am"
        if any(month in date_str.lower() for month in ['january', 'february', 'march', 'april', 'may', 'june', 
                                                    'july', 'august', 'september', 'october', 'november', 'december']):
            try:
                dt = datetime.strptime(date_str, "%B %d, %Y %I:%M %p")
                return dt.strftime("%Y-%m-%d")
            except:
                # Try without time
                try:
                    dt = datetime.strptime(date_str, "%B %d, %Y")
                    return dt.strftime("%Y-%m-%d")
                except:
                    pass
        
        # Handle Newswire format: "2023-02-02" (already ISO)
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
            
        # Try a few other common formats
        formats = [
            "%Y-%m-%d",     # 2023-01-08
            "%d/%m/%Y",     # 08/01/2023
            "%m/%d/%Y",     # 01/08/2023
            "%d-%m-%Y",     # 08-01-2023
            "%Y/%m/%d",     # 2023/01/08
            "%d.%m.%Y",     # 08.01.2023
            "%B %d, %Y",    # January 08, 2023
            "%d %B %Y",     # 08 January 2023
            "%d %b %Y",     # 08 Jan 2023
            "%b %d, %Y"     # Jan 08, 2023
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except:
                continue
                
        # If all parsing attempts fail
        print(f"Warning: Could not parse date format: '{date_str}'")
        return date_str
        
    except Exception as e:
        print(f"Error parsing date '{date_str}': {e}")
        return date_str

def vectorize_text(text):
    """Vectorize text using the sentence transformer model."""
    try:
        # Truncate text if it's too long
        max_length = 8192
        if len(text) > max_length:
            text = text[:max_length]
        
        # Generate embedding
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"Error vectorizing text: {e}")
        raise