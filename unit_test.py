import unittest
from unittest.mock import MagicMock
import os
from datetime import datetime
import json

# Assuming your agent files are in the same directory
from query_refinement_agent import QueryRefinementAgent
from output_style_agent import OutputStyleAgent
from entity_extraction_agent import EntityExtractionAgent
from relevance_agent import RelevanceAgent
from fact_verification_agent import FactVerificationAgent

class TestQueryRefinementAgent(unittest.TestCase):

    def setUp(self):
        self.mock_openai_client = MagicMock()
        self.agent = QueryRefinementAgent(openai_client=self.mock_openai_client)

    def test_generate_refined_query_success(self):
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="refined sri lanka news query"))
        ]
        original_query = "sri lanka news"
        refined_query = self.agent.generate_refined_query(original_query)
        self.assertEqual(refined_query, "refined sri lanka news query")
        self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_generate_refined_query_too_long(self):
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="a" * 400))
        ]
        original_query = "short"
        refined_query = self.agent.generate_refined_query(original_query)
        self.assertEqual(refined_query, original_query)
        self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_generate_refined_query_openai_error(self):
        self.mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI error")
        original_query = "test query"
        refined_query = self.agent.generate_refined_query(original_query)
        self.assertEqual(refined_query, original_query)
        self.mock_openai_client.chat.completions.create.assert_called_once()

class TestOutputStyleAgent(unittest.TestCase):

    def setUp(self):
        self.mock_openai_client = MagicMock()
        self.agent = OutputStyleAgent(openai_client=self.mock_openai_client)

    def test_determine_output_style_event_list(self):
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="event_list"))
        ]
        query = "what events happened"
        style = self.agent.determine_output_style(query)
        self.assertEqual(style, "event_list")
        self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_determine_output_style_default(self):
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="unknown style"))
        ]
        query = "tell me about something"
        style = self.agent.determine_output_style(query)
        self.assertEqual(style, "summary_paragraph")
        self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_format_summary_success(self):
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="formatted summary"))
        ]
        summary_text = "raw summary"
        style = "point_form"
        formatted = self.agent.format_summary(summary_text, style)
        self.assertEqual(formatted, "formatted summary")
        self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_format_summary_openai_error(self):
        self.mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI error")
        summary_text = "raw summary"
        style = "table_structure"
        formatted = self.agent.format_summary(summary_text, style)
        self.assertEqual(formatted, summary_text)
        self.mock_openai_client.chat.completions.create.assert_called_once()

class TestEntityExtractionAgent(unittest.TestCase):

    def setUp(self):
        self.mock_openai_client = MagicMock()
        self.agent = EntityExtractionAgent(openai_client=self.mock_openai_client)

    def test_extract_entities_success(self):
        mock_response_content = json.dumps({"LOCATION": ["Colombo"], "PERSON": ["Ranil"]})
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=mock_response_content))
        ]
        query = "news about Ranil in Colombo"
        entities = self.agent.extract_entities(query)
        self.assertEqual(entities, {"LOCATION": ["Colombo"], "PERSON": ["Ranil"]})
        self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_extract_entities_no_entities(self):
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="{}"))
        ]
        query = "general news"
        entities = self.agent.extract_entities(query)
        self.assertEqual(entities, {})
        self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_extract_entities_openai_error(self):
        self.mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI error")
        query = "test query"
        entities = self.agent.extract_entities(query)
        self.assertEqual(entities, {})
        self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_process_query(self):
        mock_response_content = json.dumps({"ORGANIZATION": ["Company X"]})
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=mock_response_content))
        ]
        query = "news about Company X"
        entities, all_entities = self.agent.process_query(query)
        self.assertEqual(entities, {"ORGANIZATION": ["Company X"]})
        self.assertEqual(all_entities, ["Company X"])
        self.mock_openai_client.chat.completions.create.assert_called_once()

class TestRelevanceAgent(unittest.TestCase):

    def setUp(self):
        self.mock_openai_client = MagicMock()
        self.agent = RelevanceAgent(openai_client=self.mock_openai_client)
        self.mock_openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Reasoning...\nSCORE: 0.8"))
        ]
        self.mock_openai_client.chat.completions.create.return_value.choices_reasoning_low = [
            MagicMock(message=MagicMock(content="Reasoning...\nSCORE: 0.4"))
        ]

    def test_filter_by_relevance_above_threshold(self):
        results_data = [{'ID': '1', 'Title': 'Article 1', 'Content': 'Content 1'}]
        filtered, analysis = self.agent.filter_by_relevance("test query", results_data, threshold=0.7)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(len(analysis), 1)
        self.assertEqual(analysis['1']['score'], 0.8)

    def test_filter_by_relevance_below_threshold(self):
        self.mock_openai_client.chat.completions.create.return_value.choices = self.mock_openai_client.chat.completions.create.return_value.choices_reasoning_low
        results_data = [{'ID': '1', 'Title': 'Article 1', 'Content': 'Content 1'}]
        filtered, analysis = self.agent.filter_by_relevance("test query", results_data, threshold