import json
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

# Import all agents
from query_refinement_agent import QueryRefinementAgent
from output_style_agent import OutputStyleAgent
from entity_extraction_agent import EntityExtractionAgent
from relevance_agent import RelevanceAgent
# Import the new fact verification agent
from fact_verification_agent import FactVerificationAgent

# Add this near the top of your script, after your imports
@st.cache_resource
def initialize_services():
    """Initialize all models and services with proper caching"""
    try:
        model = load_model()
        index = init_pinecone()
        openai_client = init_openai()
        
        # Initialize all agents
        query_agent = QueryRefinementAgent(openai_client)
        style_agent = OutputStyleAgent(openai_client)
        entity_agent = EntityExtractionAgent(openai_client)
        relevance_agent = RelevanceAgent(openai_client)
        fact_agent = FactVerificationAgent(openai_client)
        
        # Get index stats
        index_stats = index.describe_index_stats()
        total_vectors = index_stats['total_vector_count']
        
        return {
            "model": model,
            "index": index,
            "openai_client": openai_client,
            "query_agent": query_agent,
            "style_agent": style_agent,
            "entity_agent": entity_agent,
            "relevance_agent": relevance_agent,
            "fact_agent": fact_agent,
            "total_vectors": total_vectors
        }
    except Exception as e:
        st.error(f"Error connecting to services: {e}")
        st.stop()

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

# Initialize OpenAI client
@st.cache_resource
def init_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=api_key)

# Search function for semantic search
def search_pinecone(query, index, model, top_k=5, filter_params=None, entity_filters=None):
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

    # Merge entity filters into the main filter parameters
    if entity_filters and isinstance(entity_filters, dict):
        filter_params.update(entity_filters)
    
    # Add filter if provided
    if filter_params and filter_params != {}:
        search_params["filter"] = filter_params
        print(f"Using filter: {filter_params}")
    else:
        print("No filters applied")
    
    # Execute search
    try:
        # First, perform the vector search
        search_results = index.query(**search_params)

        # Get the initial matches
        matches = search_results.get("matches", [])
        
        # Sort matches by score in descending order
        sorted_matches = sorted(
            matches, 
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

# Function to display relevance analysis results
def display_relevance_analysis(relevance_analysis, filtered_count, total_count):
    st.subheader("Relevance Analysis")
    st.write(f"🔍 Filtered out {total_count - filtered_count} of {total_count} articles based on relevance.")
    
    # Show details in an expander
    with st.expander("See detailed relevance scores"):
        # Create a dataframe for better display
        analysis_data = []
        for article_id, data in relevance_analysis.items():
            analysis_data.append({
                'Article Title': data['title'],
                'Relevance Score': data['score'] if isinstance(data['score'], str) else f"{data['score']:.2f}",
                'Included': "✅" if (isinstance(data['score'], float) and data['score'] >= 0.7) else "❌",
                'Reasoning': data['reasoning']
            })
        
        # Convert to dataframe and display
        if analysis_data:
            df = pd.DataFrame(analysis_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No relevance analysis available.")

# Function to summarize search results using OpenAI
def summarize_with_openai(results_data, query, output_style=None):
    if not results_data or len(results_data) == 0:
        return "No results to summarize."
    
    # Get API key from environment variables with fallback
    client = init_openai()
    
    # Prepare the content for summarization
    content_to_summarize = f"""Summarize the following news articles clear and consise, 
        capturing the key events, causes, and resolutions related to Sri Lanka. Exclude unnecessary details and prioritize clarity and coherence, 
        make sure you reject any article not relate to original user query: {query}.\n\n"""
    
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
            max_tokens=800
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

def display_verification_results(verification_results):
    """
    Display verification results in a nicely formatted way using Streamlit's markdown.
    Sorts results to show verified claims first, followed by partially verified, then not verified.
    
    Args:
        verification_results (list): List of formatted verification result strings
    """
    st.markdown("###📋 Fact Verification Results")
    
    if not verification_results:
        st.warning("No verification results to display.")
        return
    
    # Sort results by verification status (Verified > Partially Verified > Not Verified)
    def get_verification_priority(result):
        if ": (Verified)" in result:
            return 0  # Highest priority
        elif ": (Partially Verified)" in result:
            return 1  # Medium priority
        else:
            return 2  # Lowest priority
    
    sorted_results = sorted(verification_results, key=get_verification_priority)
    
    # Create expandable sections for each claim
    for i, result in enumerate(sorted_results):
        # Split the result string to extract components
        # Expected format: "Claim text - [Source1](URL1), [Source2](URL2) : (Verification Status)"
        # Or: "Claim text - No supporting articles : (Verification Status)"
        
        # First split by the status indicator
        parts = result.split(" : (")
        if len(parts) != 2:
            # Handle unexpected format
            st.markdown(f"**Result {i+1}:** {result}")
            continue
            
        claim_and_sources = parts[0]
        status = parts[1].rstrip(")")  # Remove the closing parenthesis
        
        # Split claim from sources
        if " - " in claim_and_sources:
            claim, sources_text = claim_and_sources.split(" - ", 1)
        else:
            claim = claim_and_sources
            sources_text = "No supporting articles"
        
        # Set icon and color based on verification status
        if status == "Verified":
            icon = "✅"
        elif status == "Partially Verified":
            icon = "⚠️"
        else:  # Not Verified
            icon = "❌"
        
        # Create expandable section with colored header
        with st.expander(f"{icon} **Claim {i+1}**: {claim}"):
            st.markdown(f"**Status:** <span style='font-weight:bold;'>{status}</span>", unsafe_allow_html=True)
            
            if sources_text == "No supporting articles":
                st.markdown("**Sources:** No supporting articles found")
            else:
                st.markdown(f"**Supporting Sources:** {sources_text}", unsafe_allow_html=True)
            
            # Add a divider
            st.markdown("---")
            
    # Add a note about the sorting
    st.info("Results are sorted with verified claims first, followed by partially verified and unverified claims.")


# Main Streamlit application
def main():
    
    display_header()
    
    # Initialize services only once
    services = initialize_services()

    # Display connection status just once
    st.info(f"Connected to Pinecone index with {services['total_vectors']:,} documents")
    
    # Extract services from the cached result
    model = services["model"]
    index = services["index"]
    openai_client = services["openai_client"]
    query_agent = services["query_agent"]
    style_agent = services["style_agent"]
    entity_agent = services["entity_agent"]
    relevance_agent = services["relevance_agent"]
    fact_agent = services["fact_agent"]
    
    # Search input
    query = st.text_input("Enter your search query")
    
    # Agent settings
    with st.expander("Agent Settings"):
        show_agent_details = st.checkbox("Show agent analysis details", value=False)
        use_query_agent = st.checkbox("Use query refinement agent", value=True)
        use_style_agent = st.checkbox("Use output style agent", value=True)
        use_entity_agent = st.checkbox("Use entity extraction agent", value=True)
        use_relevance_agent = st.checkbox("Use relevance filtering agent", value=True)
        # Add checkbox for the new fact verification agent
        use_fact_agent = st.checkbox("Use fact verification agent", value=True)
        
        # Show output style options if style agent is disabled
        if not use_style_agent:
            output_styles = [
                "Auto-detect",
                "Event List",
                "Summary Paragraph",
                "Table Structure", 
                "Point Form List",
                "Question & Answer",
                "Timeline"
            ]
            selected_style = st.selectbox("Output Format", output_styles)
            
            # Map the user-friendly names to the internal style names
            style_mapping = {
                "Auto-detect": None,
                "Event List": "event_list",
                "Summary Paragraph": "summary_paragraph",
                "Table Structure": "table_structure",
                "Point Form List": "point_form",
                "Question & Answer": "question_answer",
                "Timeline": "timeline"
            }
            output_style = style_mapping[selected_style]
        else:
            output_style = None  # Will be determined by the style agent
        
        # Add relevance threshold slider if relevance agent is enabled
        if use_relevance_agent:
            relevance_threshold = st.slider(
                "Relevance threshold", 
                min_value=0.1, 
                max_value=1.0, 
                value=0.5, 
                step=0.1,
                help="Articles with relevance scores below this threshold will be filtered out"
            )
    
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
    search_clicked = st.button("Search")
    if search_clicked:
        if not query:
            st.warning("Please enter a search query")
        else:
            with st.spinner("Searching..."):
                # Build filter as a dictionary
                filter_params = {}
                
                # If source is selected, add it to filters
                if selected_source != "All Sources":
                    filter_params["source_db"] = selected_source
                
                # Initialize variables for entity filtering
                entity_filters = []
                entities = {}
                
                # Process the query through the entity extraction agent if enabled
                if use_entity_agent:
                    with st.spinner("Extracting entities from query..."):
                        # Process the query through the entity agent
                        entities, entity_filters = entity_agent.process_query(query)
                        
                        # Show entity agent analysis if enabled
                        if show_agent_details and entities:
                            st.subheader("Entity Agent Analysis")
                            
                            # Display extracted entities
                            st.markdown("#### Extracted Entities")
                            for entity_type, entity_list in entities.items():
                                if entity_list:
                                    st.markdown(f"**{entity_type}:** {', '.join(entity_list)}")
                        
                        all_entities = []

                        for entity_type, entity_list in entities.items():
                            if entity_list:
                                all_entities.extend([entity.lower() for entity in entity_list])

                        if all_entities:
                            filter_params["keywords"] = {"$in": all_entities}

                # Use the query refinement agent if enabled
                if use_query_agent:
                    with st.spinner("Agent refining query..."):
                        # Refine the query using the agent
                        refined_query = query_agent.generate_refined_query(query)
                        
                        # Show agent analysis if enabled
                        if show_agent_details:
                            st.subheader("Query Agent Analysis")
                            
                            # Display original vs refined query
                            st.markdown("#### Query Refinement")
                            st.markdown(f"**Original query:** {query}")
                            st.markdown(f"**Refined query:** {refined_query}")
                        
                        # Use the refined query for search
                        search_query = refined_query
                else:
                    search_query = query
                
                try:
                    # Execute the search with entity filters if enabled
                    results = search_pinecone(search_query, index, model, top_k, filter_params, 
                                             entity_filters if use_entity_agent else None)
                    results_data = process_results(results)
                    
                    # Ensure we have the requested number of results
                    results_data = results_data[:top_k]
                    
                    # Add relevance filtering if enabled
                    if use_relevance_agent and results_data:
                        with st.spinner("Evaluating article relevance..."):
                            # Store original count for comparison
                            original_count = len(results_data)
                            
                            # Apply relevance filtering
                            filtered_results, relevance_analysis = relevance_agent.filter_by_relevance(
                                query, 
                                results_data,
                                threshold=relevance_threshold
                            )
                            
                            # Update the results data with filtered results
                            results_data = filtered_results
                            
                            # Show relevance analysis if enabled
                            if show_agent_details:
                                display_relevance_analysis(
                                    relevance_analysis, 
                                    len(filtered_results), 
                                    original_count
                                )

                    # Add summary if we have results (before displaying the individual links)
                    if results_data and len(results_data) > 0:
                        # Display number of results found
                        st.success(f"Found {len(results_data)} relevant results")
                        
                        with st.spinner("Generating summary..."):
                            # Determine output style if style agent is enabled
                            if use_style_agent:
                                output_style = style_agent.determine_output_style(query, results_data)
                                
                                # Show style agent analysis if enabled
                                if show_agent_details:
                                    st.subheader("Style Agent Analysis")
                                    st.markdown(f"**Recommended output style:** {output_style.replace('_', ' ').title()}")
                            
                            # Get the summary with the selected/determined output style
                            summary = summarize_with_openai(results_data, query, output_style)

                            # Format the summary if style agent is enabled but not already handled in summarize_with_openai
                            if use_style_agent and output_style:
                                # Show the style being used
                                st.markdown(f"### News Summary ({output_style.replace('_', ' ').title()} Format)")
                                st.markdown(summary)
                            else:
                                # Display the summary
                                st.markdown(f"### News Summary")
                                st.markdown(summary)

                            if use_fact_agent and results_data:
                                verification_summary = []  # Initialize as a list instead
                                with st.spinner("Fact verification..."):
                                    claims = fact_agent.extract_claims_from_summary(summary)
                                    print(claims)
                                    verification_result = fact_agent.verify_claims_in_articles(claims, results_data)
                                        # Simply append the result (whether it's a string or list)
                                    display_verification_results(verification_result)

                        # Now display the detailed results
                        display_results(results_data)
                    else:
                        st.warning("No results found that match your query criteria")
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