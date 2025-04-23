import os
import sys
import argparse
from dotenv import load_dotenv
import json
from bson import json_util
import spacy
from collections import Counter

# Import modules from local files
from config import load_config

# Load environment variables
load_dotenv()

class EntityExtractionAgentSpaCy:
    def __init__(self, model_name="en_core_web_lg"):
        """
        Initialize the entity extraction agent with a spaCy model.
        
        Args:
            model_name: Name of the spaCy model to load (default: en_core_web_lg)
        """
        try:
            self.nlp = spacy.load(model_name)
            print(f"Successfully loaded spaCy model: {model_name}")
        except Exception as e:
            print(f"Error loading spaCy model: {e}")
            raise

    def process_article_entities(self, text):
        """
        Process text to extract specific named entities.
        
        Args:
            text: String content to process
            
        Returns:
            List of extracted entity strings in lowercase
        """
        try:
            # Ensure text is a string
            if not isinstance(text, str):
                if isinstance(text, list):
                    text = ' '.join([str(item) for item in text if item])
                else:
                    text = str(text)
            
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Define entity mapping
            entity_mapping = {
                "PERSON": "PERSON",
                "ORG": "ORGANIZATION",
                "GPE": "LOCATION",  # Countries, cities, states
                "LOC": "LOCATION",  # Non-GPE locations
                "FAC": "LOCATION",  # Facilities, buildings, airports, highways
                "EVENT": "EVENT"
            }
            
            # Extract only specific entity types
            filtered_entities = []
            
            for ent in doc.ents:
                # Map spaCy entity type to our desired categories
                mapped_type = entity_mapping.get(ent.label_)
                
                # Only keep entities of specified types
                if mapped_type:
                    # Clean up entity text and convert to lowercase
                    entity_text = ent.text.strip().lower()
                    if entity_text and len(entity_text) > 1 and entity_text not in filtered_entities:
                        filtered_entities.append(entity_text)
            
            # Return just the list of filtered entities
            return filtered_entities
        
        except Exception as e:
            print(f"Error in entity extraction: {e}")
            return []


def initialize_entity_extraction_agent(model_name=None):
    config = load_config()
    
    # Use model from config if not specified
    if model_name is None and config and 'spacy_model' in config:
        model_name = config.get('spacy_model')
    
    # Default to larger English model if still not specified
    if model_name is None:
        model_name = "en_core_web_lg"
    
    try:
        agent = EntityExtractionAgentSpaCy(model_name)
        print("Successfully initialized entity extraction agent")
        return agent
    except Exception as e:
        print(f"Failed to initialize entity extraction agent: {e}")
        print("Entity extraction will be skipped")
        return None