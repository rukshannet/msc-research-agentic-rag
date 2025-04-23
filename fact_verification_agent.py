# simple_fact_verification.py
import re

class FactVerificationAgent:
    """
    Agent that verifies facts by checking claims across multiple articles
    without implementing consensus scoring mechanisms.
    """
    
    def __init__(self, openai_client):
        """
        Initialize the fact verification agent with an OpenAI client.
        
        Args:
            openai_client: An initialized OpenAI client
        """
        self.openai_client = openai_client
        
    def extract_claims_from_summary(self, summary_text):
        """
        Extracts distinct factual claims from a summary.
        
        Args:
            summary_text (str): The summary text to analyze
            
        Returns:
            list: List of distinct factual claims
        """
        prompt = f"""
        Please identify all distinct factual claims in the following news summary.
        For each claim, extract it as a simple, atomic statement of fact.
        Focus on specific facts, events, dates, numbers, people, and places.
        Do not include opinions, generalizations, or interpretations.
        
        Summary:
        {summary_text}
        
        Output each factual claim on a new line starting with "CLAIM: "
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a fact extraction assistant that identifies specific factual claims from text."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            
            # Extract claims from the response
            response_text = response.choices[0].message.content
            claims = [line.replace("CLAIM: ", "").strip() for line in response_text.split("\n") if line.strip().startswith("CLAIM:")]
            
            return claims
            
        except Exception as e:
            print(f"Error extracting claims: {e}")
            return []
        
    def verify_claims_in_articles(self, claims, articles):
        """
        Verifies multiple claims across multiple articles efficiently.
        Processes each article once for all claims rather than checking each claim separately.
        
        Args:
            claims (list): List of claims to verify
            articles (list): List of article dictionaries
            
        Returns:
            list: List of formatted verification results, one for each claim
        """
        # Initialize results dictionary for each claim
        verification_results = {claim: [] for claim in claims}
        
        # Process each article once
        for i, article in enumerate(articles):
            article_title = article.get("Title", "Untitled")
            article_content = article.get("Content", "")
            article_id = article.get("ID", f"article_{i}")
            article_source = article.get("Source", "Unknown")
            article_url = article.get("URL", "#")
            
            # Create a batch prompt to verify all claims at once for this article
            claims_text = "\n".join([f"Claim {j+1}: \"{claim}\"" for j, claim in enumerate(claims)])
            
            prompt = f"""
            Task: Verify if the following claims are supported by the article content.
            
            {claims_text}
            
            Article title: "{article_title}"
            
            Article content:
            "{article_content}..." (truncated)
            
            For EACH claim, assess if it is:
            1. DIRECTLY SUPPORTED: The article explicitly states this claim
            2. INDIRECTLY SUPPORTED: The article implies this or contains facts that support this claim
            3. NOT SUPPORTED: The article does not mention anything related to this claim
            4. CONTRADICTED: The article contains information that contradicts this claim
            
            For each claim, provide:
            1. The claim number
            2. Your reasoning
            3. A line with "VERIFICATION: X" where X is one of the four categories above
            
            Separate each claim's analysis with "---"
            """
            
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a fact verification assistant that carefully evaluates if claims are supported by source documents."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000
                )
                
                response_text = response.choices[0].message.content
                
                # Split the response by claim sections
                claim_sections = response_text.split("---")
                
                # Process each claim section
                for j, claim in enumerate(claims):
                    # Find the matching section for this claim (looking for "Claim j+1" or fallback to position)
                    matching_sections = [s for s in claim_sections if f"Claim {j+1}" in s]
                    section = matching_sections[0] if matching_sections else (claim_sections[j] if j < len(claim_sections) else "")
                    
                    if section:
                        # Extract verification status
                        verification_match = re.search(r"VERIFICATION:\s*(DIRECTLY SUPPORTED|INDIRECTLY SUPPORTED|NOT SUPPORTED|CONTRADICTED)", section)
                        verification_status = verification_match.group(1) if verification_match else "UNKNOWN"
                        
                        # Extract reasoning (everything before VERIFICATION:)
                        reasoning = section.split("VERIFICATION:")[0].strip() if "VERIFICATION:" in section else section
                        
                        # Store results for this claim
                        verification_results[claim].append({
                            "article_id": article_id,
                            "article_title": article_title,
                            "article_source": article_source,
                            "article_url": article_url,
                            "verification_status": verification_status,
                            "reasoning": reasoning
                        })
                    else:
                        # If we couldn't find a section for this claim
                        verification_results[claim].append({
                            "article_id": article_id,
                            "article_title": article_title,
                            "article_source": article_source,
                            "article_url": article_url,
                            "verification_status": "UNKNOWN",
                            "reasoning": "Could not extract verification for this claim"
                        })
                    
            except Exception as e:
                print(f"Error verifying claims in article {article_id}: {e}")
                # Add error result for each claim
                for claim in claims:
                    verification_results[claim].append({
                        "article_id": article_id,
                        "article_title": article_title,
                        "article_source": article_source,
                        "article_url": article_url,
                        "verification_status": "ERROR",
                        "reasoning": f"Error during verification: {str(e)}"
                    })
        
        # Format final results for each claim
        final_results = []
        
        for claim, results in verification_results.items():
            # Count supporting articles
            supporting_articles = []
            for result in results:
                if result["verification_status"] in ["DIRECTLY SUPPORTED", "INDIRECTLY SUPPORTED"]:
                    # Create a source link in format: Source(URL)
                    source_link = f"[{result['article_source']}]({result['article_url']})"
                    supporting_articles.append(source_link)
            
            # Determine verification status
            if len(supporting_articles) >= 2:
                verification_status = "Verified"
            elif len(supporting_articles) == 1:
                verification_status = "Partially Verified"
            else:
                verification_status = "Not Verified"
            
            # Format the result string
            supporting_articles_str = ", ".join(supporting_articles)
            if supporting_articles:
                result_str = f"{claim} - {supporting_articles_str} : ({verification_status})"
            else:
                result_str = f"{claim} - No supporting articles : ({verification_status})"
            
            final_results.append(result_str)
        
        return final_results
    