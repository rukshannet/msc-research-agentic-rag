import re
from datetime import datetime
import openai
from openai import OpenAI
import pandas as pd
import os

class QueryRefinementAgent:
    
    def __init__(self, openai_client=None):
        self.client = openai_client if openai_client else OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        current_year = datetime.now().year
    
    
    def generate_refined_query(self, original_query):
        """Use OpenAI to refine the query based on its semantic meaning"""
        try:
            prompt = (
                "You are a search query optimization agent. Your task is to refine and improve search queries "
                "about Sri Lanka news to make them more effective for vector search. Enhance specificity, add context, "
                "and clarify ambiguities. Keep the query concise. Return ONLY the refined query without explanations, "
                "and do not add any year or number randomly to the qyery"
            )

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Original query: {original_query}"}
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            refined_query = response.choices[0].message.content.strip()
            
            # If the refinement drastically changed the query, revert to original
            if len(refined_query) > len(original_query) * 3:
                return original_query
                
            return refined_query
            
        except Exception as e:
            print(f"Error refining query with OpenAI: {e}")
            return original_query