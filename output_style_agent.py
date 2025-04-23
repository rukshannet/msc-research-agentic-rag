class OutputStyleAgent:
    
    def __init__(self, openai_client=None):
        self.client = openai_client if openai_client else OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.styles = {
            "event_list": "A chronologically ordered list of events with dates",
            "summary_paragraph": "A concise paragraph summarizing the key information",
            "table_structure": "A structured table with dates, events, and outcomes",
            "point_form": "A bulleted list of key information points",
            "question_answer": "A Q&A format addressing key aspects of the topic",
            "timeline": "A chronological timeline of events"
        }
    
    def determine_output_style(self, query, results_data=None):
        """
        Determine the best output style based on the user query and the search results
        
        Args:
            query (str): The user's search query
            results_data (list, optional): The search results data
            
        Returns:
            str: The recommended output style
        """
        try:
            # Create a prompt that explains what we're trying to do
            prompt = (
                "You are an output format recommendation agent. Based on the user's search query "
                "and the type of information they're looking for, suggest the most appropriate "
                "output format from the following options:\n\n"
                "1. event_list: A chronologically ordered list of events with dates\n"
                "2. summary_paragraph: A concise paragraph summarizing the key information\n"
                "3. table_structure: A structured table with dates, events, and outcomes\n"
                "4. point_form: A bulleted list of key information points\n"
                "5. question_answer: A Q&A format addressing key aspects of the topic\n"
                "6. timeline: A chronological timeline of events\n\n"
                "Consider what would be most helpful for the user based on their query. "
                "Respond with ONLY the format name (e.g., 'event_list', 'summary_paragraph', etc.)"
            )
            
            # Include information about the query
            context = f"User query: {query}\n\n"
            
            # Add information about the search results if available
            if results_data and len(results_data) > 0:
                context += "Search returned articles about: "
                titles = [item['Title'] for item in results_data[:3]]
                context += ", ".join(titles) + "\n"
            
            # Create the completion
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context}
                ],
                max_tokens=20,
                temperature=0.3
            )
            
            # Extract the recommended style
            suggested_style = response.choices[0].message.content.strip().lower()
            
            # Clean up the response (remove any non-style text)
            for style in self.styles.keys():
                if style in suggested_style:
                    return style
            
            # Default to summary_paragraph if we couldn't recognize the style
            return "summary_paragraph"
            
        except Exception as e:
            print(f"Error determining output style: {e}")
            return "summary_paragraph"  # Default to summary paragraph on error
    
    def format_summary(self, summary_text, style):
        """
        Format the summary text according to the specified style
        
        Args:
            summary_text (str): The raw summary text from the LLM
            style (str): The output style to format to
            
        Returns:
            str: The formatted summary
        """
        try:
            prompt = (
                f"You are a content formatting specialist. Take the following summary about Sri Lanka news "
                f"and reformat it into a {self.styles.get(style, 'concise summary')}. "
                f"Maintain all the important information but reorganize it according to the {style} format. "
                f"Be clear, concise, and focus on the key details. "
                f"Apply proper formatting like bullet points, headers, or tables as appropriate for the {style} format."
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": summary_text}
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            formatted_summary = response.choices[0].message.content.strip()
            return formatted_summary
            
        except Exception as e:
            print(f"Error formatting summary: {e}")
            return summary_text  # Return original summary on error