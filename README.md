# MScResearch
MSc Research repo

This repository contains the code for my MSc Research project, focusing on building a Retrieval-Augmented Generation (RAG) system. The system scrapes news from three different sources (NewsWire, NewsFirst, and AdaDerana), saves the scraped news in MongoDB for easy access, creates embeddings and saves them in Pinecone Database. It uses agents to process user queries and results, displays results with better formatting, and shows fact verification details.


## Application Flow

1.  **User Input:** The process begins when the user enters a query or claim.
    *Example:* “What happen to CEB restructuring process ?”
2.  **Query Refinement Agent Processing:** The Query Refinement agent receives the raw query. It decides whether refinement is needed.
    *Example:* Refined query “Current status of the CEB restructuring process in Sri Lanka”
3.  **Entity Extraction Agent Processing:** The refined query is then passed to the Entity Extraction module. This could use a Named Entity Recognition (NER) model or the LLM to identify entities. (Organization, Person, Location, Event)
    *Example:* Organization: CEB
4.  **Retrieval Agent – Vector DB Search:** Using the refined query and extracted entities, the retrieval component formulates a search. For the vector database, it generates an embedding of the query and performs similarity search. It might also include keywords as well.
    *Example:* Found 5 relevant results
5.  **Relevance Filtering Agent:** Ranking them by a combination of similarity score and presence of key entities. Each article is check against the user query with LLM support.
    *Example:* Filtered out 0 of 5 articles based on relevance.
6.  **Output Style Agent:** System decide the answer style to present to end user according to user query, such as paragraph, event list, summary, point format.
    *Example:* Recommended output style: Summary Paragraph
7.  **Fact Verification Agent:** From the answer agent generates claims that needs to be verified and checked against news articles for verification:
    *Example:*
    *   Claim 1: The CEB's restructuring encompasses unbundling, audits, human resource management, and integrating renewable energy.
        *   Status: Verified
        *   Supporting Sources: Newswire and AdaDerana
    *   Claim 6: On February 23, 2023, Minister of Power and Energy Kanchana Wijesekera held a meeting with international development agencies including the ADB, World Bank, and JICA.
        *   Status: Partially Verified
        *   Supporting Sources: Newswire
8.  **Final Answer to User:** The processed, verified answer is sent to the user interface, where the user can read it and click on reference to see the original source material.
