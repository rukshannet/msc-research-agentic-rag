import os
import json
from openai import OpenAI

from config import load_config

class EntityExtractionAgent:
    
    def __init__(self, openai_client=None):
        self.client = openai_client if openai_client else OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.entity_types = {
            "PERSON": "People, including fictional characters",
            "LOCATION": "Countries, cities, states, mountains, bodies of water, etc.",
            "ORGANIZATION": "Companies, agencies, institutions, etc.",
            "EVENT": "Named events such as festivals, wars, sports events, etc.",
        }
    
    def extract_entities(self, text):
        """
        Extract named entities from the article text
        
        Args:
            text (str): The article text
            
        Returns:
            dict: Dictionary containing extracted entities categorized by type
        """
        try:
            # Only use first 2000 characters to keep within OpenAI context limits and reduce costs
            # For a full implementation, you would need to process the text in chunks
            text_to_analyze = text[:2000]
            
            prompt = (
                "You are an entity extraction specialist. Analyze the following text from a news article "
                "and identify any named entities present, categorizing them by type. Use the following categories:\n\n"
                "PERSON: Real people or fictional characters\n"
                "LOCATION: Countries, cities, states, mountains, bodies of water, etc.\n"
                "ORGANIZATION: Companies, agencies, institutions, etc.\n"
                "Return your answer as a JSON object with entity types as keys and arrays of extracted entities as values. "
                "Only include categories where entities were found. If no entities are found, return an empty JSON object {}."
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Article text: {text_to_analyze}"}
                ],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.1
            )
            
            # Extract and parse the JSON response
            entities_json = response.choices[0].message.content.strip()
            entities = json.loads(entities_json)
            
            return entities
            
        except Exception as e:
            print(f"Error extracting entities: {e}")
            return {}  # Return empty dict on error
    
    def get_all_entities_as_list(self, entities_dict):
        """Convert entities dictionary to a flat list of all entities in lowercase"""
        all_entities = []
        for entity_type, entity_list in entities_dict.items():
            all_entities.extend([entity.lower() for entity in entity_list])
        return list(set(all_entities))  # Remove duplicates

def initialize_entity_extraction_agent():
    """Initialize the entity extraction agent if API key exists."""
    config = load_config()
    openai_api_key = config["OPENAI_API_KEY"]
    
    if not openai_api_key:
        print("Warning: OpenAI API key not found. Entity extraction will be skipped.")
        return None
    
    try:
        openai_client = OpenAI(api_key=openai_api_key)
        agent = EntityExtractionAgent(openai_client)
        print("Successfully initialized entity extraction agent")
        return agent
    except Exception as e:
        print(f"Failed to initialize entity extraction agent: {e}")
        print("Entity extraction will be skipped")
        return None