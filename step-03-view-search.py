import streamlit as st
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
import os
from datetime import datetime
import pandas as pd
import openai
from openai import OpenAI
import sys
from dotenv import load_dotenv
import warnings
import base64

# Load environment variables from .env file
load_dotenv()

# Initialize Sentence Transformer model
@st.cache_resource
def load_model():
    # Suppress specific warning messages from SentenceTransformer
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        return SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')

# Initialize Pinecone connection with the updated SDK
def init_pinecone():
    # Get API keys from environment variables
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME")
    
    # Initialize Pinecone client
    pc = Pinecone(api_key=api_key)
    
    # Get the index
    return pc.Index(index_name)

# Search function for semantic search
def search_pinecone(query, index, model, top_k=5, filter_params=None):
    # Normalize and preprocess query if needed
    query = query.strip()
    
    # Encode query to get dense vector
    query_vector = model.encode(query).tolist()
    
    # Search parameters - retrieve more results initially
    search_params = {
        "vector": query_vector,
        "top_k": 30,  # Get 30 results instead of just 5
        "include_metadata": True
    }
    
    # Add filter if provided
    if filter_params and filter_params != {}:
        search_params["filter"] = filter_params
        print(f"Using filter: {filter_params}")
    else:
        print("No filters applied")
    
    # Execute search
    try:
        search_results = index.query(**search_params)
        
        # Sort matches by score in descending order
        sorted_matches = sorted(
            search_results["matches"], 
            key=lambda x: x["score"], 
            reverse=True
        )
        
        # Take only the top k after sorting
        search_results["matches"] = sorted_matches[:top_k]
        
        return search_results
    except Exception as e:
        print(f"Error during Pinecone search: {e}")
        return {"matches": []}

# Function to process results data without displaying
def process_results(results):
    if not results.get('matches'):
        return []
    
    results_data = []
    for match in results['matches']:
        # Correctly access the metadata fields based on our storage format
        date_str = match['metadata'].get('date', 'N/A')
        
        # Try to format the date, if possible
        try:
            # Our date format from the storage script is YYYY-MM-DD
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime('%B %d, %Y')
        except ValueError:
            formatted_date = date_str
            
        result = {
            'Title': match['metadata'].get('title', 'N/A'),
            'Content': match['metadata'].get('content', 'N/A'),
            'Date': formatted_date,
            'URL': match['metadata'].get('url', 'N/A'),  
            'Similarity Score': match['score'],
            'ID': match['id'],
            'Source': match['metadata'].get('source_db', 'Unknown')  # Add source database
        }
        results_data.append(result)
    
    return results_data

# Function to display results (separate from processing)
def display_results(results_data):
    if not results_data:
        st.warning("No results found")
        return
    
    # Create DataFrame for better display
    df = pd.DataFrame(results_data)
    
    # Display each result in an expandable container
    for i, row in df.iterrows():
        with st.expander(f"{i+1}. {row['Title']} - {row['Date']}"):
            st.write(f"**Score:** {row['Similarity Score']:.4f}")
            st.write(f"**Source:** {row['Source']}")
            st.write(f"**Document ID:** {row['ID']}")
            st.markdown(f"[View Original Article]({row['URL']})")

# Function to summarize search results using OpenAI
def summarize_with_openai(results_data,query):
    if not results_data or len(results_data) == 0:
        return "No results to summarize."
    
    # Get API key from environment variables with fallback
    api_key = os.getenv("OPENAI_API_KEY")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Prepare the content for summarization
    #content_to_summarize = "Summarize the following news articles into a single concise paragraph, capturing the key events, causes, and resolutions related to Sri Lanka, Exclude unnecessary details and prioritize clarity and coherence:\n\n"
    content_to_summarize = f"Summarize the following news articles into events list include dates or months which event took place, capturing the key events, causes, and resolutions related to Sri Lanka, Exclude unnecessary details and prioritize clarity and coherence, make sure you reject any article not relate to original user query :{query} \n\n"
    

    for i, result in enumerate(results_data):
        content_to_summarize += f"Article {i+1}: {result['Title']}\n"
        content_to_summarize += f"Date: {result['Date']}\n"
        content_to_summarize += f"Source: {result['Source']}\n"
        content_to_summarize += f"URL: {result['URL']}\n\n"
        content_to_summarize += f"Content: {result['Content']}\n\n" 

    try:
        # Call OpenAI API for summarization
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes news articles."},
                {"role": "user", "content": content_to_summarize}
            ],
            max_tokens=500
        )
        
        # Extract and return the summary
        summary = response.choices[0].message.content
        return summary
    
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def display_header():
    try:
        # Create two columns - one for logo, one for title
        col1, col2 = st.columns([1, 4])
        
        # Display logo in the first column
        with col1:
            if os.path.exists("lankadigest_logo.png"):
                st.image("lankadigest_logo.png", width=120, use_container_width=False)
        # Display title in the second column with vertical alignment
        with col2:
            st.markdown('<h1 style="margin-top: 5px;">LankaDigest</h1>', unsafe_allow_html=True)
            st.markdown('<h6 style="margin-top: 1px;">AI-powered easy-to-consume news summaries about Sri Lanka</h6>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not display header: {e}")
        # Fallback to simple title
        st.title("LankaDigest")
        st.write("AI-powered easy-to-consume news summaries about Sri Lanka")

# Main Streamlit application
def main():
    # Set page title
    display_header()
    
    # Load model and initialize Pinecone
    with st.spinner("Initializing search engine..."):
        try:
            model = load_model()
            index = init_pinecone()
            index_stats = index.describe_index_stats()
            total_vectors = index_stats['total_vector_count']
            st.info(f"Connected to Pinecone index with {total_vectors:,} documents")
        except Exception as e:
            st.error(f"Error connecting to services: {e}")
            st.stop()
    
    # Search input
    query = st.text_input("Enter your search query")
    
    # Filter options
    with st.expander("Advanced Filters"):
        # Date filtering as text inputs
        st.caption("Note: Filtering by date only works if the data was indexed with dates in YYYY-MM-DD format")
        start_date = st.text_input("Start Date (YYYY-MM-DD)", "2023-01-01")
        end_date = st.text_input("End Date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
        
        # Add source filter options based on the databases we know exist from the first script
        source_options = ["All Sources", "newsfirst_data", "newswire_data", "adaderana_data"]
        selected_source = st.selectbox("Source Database", source_options)

    top_k = st.slider("Number of results to show", min_value=1, max_value=30, value=5)
    
    # Search button
    if st.button("Search") or query:
        if not query:
            st.warning("Please enter a search query")
        else:
            with st.spinner("Searching..."):
                # Build filter as a dictionary
                filter_params = {}
                
                # Note: Pinecone requires numeric values for $gte/$lte operators
                # We'll use a metadata filter without operators first
                
                # If source is selected, add it to filters
                if selected_source != "All Sources":
                    filter_params["source_db"] = selected_source
                
                try:
                    # First, try a simple search without date filtering
                    # to see what data actually looks like
                    results = search_pinecone(query, index, model, top_k, filter_params)
                    results_data = process_results(results)
                    
                    # Add summary if we have results (before displaying the individual links)
                    if results_data and len(results_data) > 0:
                        # Display number of results found
                        st.success(f"Found {len(results_data)} relevant results")
                        
                        with st.spinner("Generating summary..."):
                            # Get the summary
                            summary = summarize_with_openai(results_data,query)
                            
                            # Display the summary
                            st.markdown(f"### News Summary\n{summary}")
                        
                        # Now display the detailed results
                        display_results(results_data)
                    else:
                        st.warning("No results found")
                except Exception as e:
                    st.error(f"Error on main: {e}")
                    st.stop()
# Run the application
if __name__ == "__main__":
    # Suppress specific warning messages
    warnings.filterwarnings("ignore", category=UserWarning)
    
    # Set working directory to script location to handle file paths
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run the main function
    main()