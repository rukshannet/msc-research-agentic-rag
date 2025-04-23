import os

from openai import OpenAI


class EntityExtractionAgent:
    
    def __init__(self, openai_client=None):
        self.client = openai_client if openai_client else OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.entity_types = {
            "PERSON": "People, including fictional characters",
            "LOCATION": "Countries, cities, states, mountains, bodies of water, etc.",
            "ORGANIZATION": "Companies, agencies, institutions, etc.",
            "EVENT": "Named events such as festivals, wars, sports events, etc.",
            "DATE": "Absolute or relative dates or periods",
            "FACILITY": "Buildings, airports, highways, bridges, etc.",
            "PRODUCT": "Objects, vehicles, foods, etc. (Not services)",
            "WORK_OF_ART": "Titles of books, songs, etc."
        }
    
    def extract_entities(self, query):
        """
        Extract named entities from the user query
        
        Args:
            query (str): The user's search query
            
        Returns:
            dict: Dictionary containing extracted entities categorized by type
        """
        try:
            prompt = (
                "You are an entity extraction specialist. Analyze the following query and identify any named entities "
                "present, categorizing them by type. Focus on entities that would be important for searching "
                "news articles about Sri Lanka. Use the following categories:\n\n"
                "PERSON: Real people or fictional characters\n"
                "LOCATION: Countries, cities, states, mountains, bodies of water, etc.\n"
                "ORGANIZATION: Companies, agencies, institutions, etc.\n"
                "EVENT: Named events such as festivals, wars, sports events, etc.\n"
                "DATE: Absolute or relative dates or periods\n"
                "FACILITY: Buildings, airports, highways, bridges, etc.\n"
                "PRODUCT: Objects, vehicles, foods, etc. (Not services)\n"
                "WORK_OF_ART: Titles of books, songs, etc.\n\n"
                "Return your answer as a JSON object with entity types as keys and arrays of extracted entities as values. "
                "Only include categories where entities were found. If no entities are found, return an empty JSON object {}."
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Query: {query}"}
                ],
                response_format={"type": "json_object"},
                max_tokens=300,
                temperature=0.1
            )
            
            # Extract and parse the JSON response
            import json
            entities_json = response.choices[0].message.content.strip()
            entities = json.loads(entities_json)
            
            return entities
            
        except Exception as e:
            print(f"Error extracting entities: {e}")
            return {}  # Return empty dict on error
        
    def process_query(self, query):

        # Extract entities from the query
        entities = self.extract_entities(query)
        
        all_entities = []
        for entity_type, entity_list in entities.items():
            all_entities.extend(entity_list)

        return entities, all_entities