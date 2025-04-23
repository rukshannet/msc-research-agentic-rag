# relevance_agent.py
import json

class RelevanceAgent:
    """
    Agent that checks the relevance of news articles against the user's query
    using OpenAI's LLM capabilities.
    """
    
    def __init__(self, openai_client):
        """
        Initialize the relevance agent with an OpenAI client.
        
        Args:
            openai_client: An initialized OpenAI client
        """
        self.openai_client = openai_client
    
    def filter_by_relevance(self, query, results_data, threshold=0.7):
        """
        Filters a list of article results by checking their relevance to the user query.
        
        Args:
            query (str): The original user query
            results_data (list): List of article dictionaries containing Title, Content, etc.
            threshold (float): The minimum relevance score (0-1) required to keep an article
            
        Returns:
            tuple: (filtered_results, relevance_analysis)
                - filtered_results: List of articles that passed the relevance check
                - relevance_analysis: Dictionary of article IDs mapped to their relevance scores and reasoning
        """
        if not results_data:
            return [], {}
        
        # Create a detailed relevance analysis
        relevance_analysis = {}
        filtered_results = []
        
        for result in results_data:
            # Extract key information from the article
            article_id = result['ID']
            title = result['Title']
            content = result['Content']
            
            # Truncate content for API efficiency (can be adjusted based on token limits)
            content_preview = content[:1000] + "..." if len(content) > 1000 else content
            
            # Create the relevance evaluation prompt
            prompt = f"""
            Task: Evaluate if this article is relevant to the user's query.
            
            User Query: "{query}"
            
            Article Title: "{title}"
            
            Article Content Preview: 
            "{content_preview}"
            
            Provide a relevance score from 0 to 1, where:
            - 0.0-0.3: Not relevant at all
            - 0.4-0.6: Somewhat relevant but missing key aspects
            - 0.7-1.0: Highly relevant to the query
            
            First provide your reasoning, then on a new line, output only 'SCORE: X.X' (a number between 0 and 1).
            """
            
            try:
                # Call OpenAI API to evaluate relevance
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",  # Can be adjusted based on requirements
                    messages=[
                        {"role": "system", "content": "You are an expert news curator that accurately evaluates if articles are relevant to user queries."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300
                )
                
                # Extract the relevance score and reasoning from the response
                result_text = response.choices[0].message.content
                
                # Parse the score from the format "SCORE: X.X"
                try:
                    # Find the score line
                    score_line = [line for line in result_text.split('\n') if 'SCORE:' in line]
                    if score_line:
                        # Extract just the number
                        score_text = score_line[0].split('SCORE:')[1].strip()
                        relevance_score = float(score_text)
                    else:
                        # Fallback if format isn't followed
                        relevance_score = 0.5
                    
                    # Get the reasoning (all text before the SCORE line)
                    reasoning = result_text.split('SCORE:')[0].strip()
                    
                except Exception as e:
                    print(f"Error parsing relevance score: {e}")
                    relevance_score = 0.5
                    reasoning = "Error parsing score. " + result_text
                
                # Store the analysis
                relevance_analysis[article_id] = {
                    'score': relevance_score,
                    'reasoning': reasoning,
                    'title': title
                }
                
                # Add to filtered results if it meets the threshold
                if relevance_score >= threshold:
                    filtered_results.append(result)
                
            except Exception as e:
                print(f"Error evaluating article relevance: {e}")
                # If there's an error, include the article by default
                filtered_results.append(result)
                relevance_analysis[article_id] = {
                    'score': 'Error',
                    'reasoning': f"Error during evaluation: {str(e)}",
                    'title': title
                }
        
        return filtered_results, relevance_analysis