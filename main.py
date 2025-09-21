"""
Author: Yap

Descriptions:
1. Set your API key in the local environment.
    - If you are using VSCode, under the terminal, set the OPENAI API Key by typing "$env:OPENAI_API_KEY = 'Replace API KEY HERE'"
2. After setting up the API key, you should be running it without error.
3. Otherwise, check your working directory is correctly set up.
"""



from SchemaDataExtractor import DatabaseExtractor
from LLMAgent import LLMKGAgent
import json
import os
from GraphCreation import GraphCreation
from kgscreate import MetaGraphBuilder


extractor = DatabaseExtractor()
schema = extractor.extract_schema("cinema.sqlite")
print(schema)
print("\n")

data = extractor.extract_data("cinema.sqlite",limit=30)
print("\n")


# Initialize agent and model
LLMAgent = LLMKGAgent(model="gpt-5-mini")

graph_json = LLMAgent.generate_kgs(schema)

print(json.dumps(graph_json,indent=2))

# Build metagraph
builder = MetaGraphBuilder("bolt://localhost:7687", "neo4j", "ReplacePasswordHere")

# Clean database before creating
builder.reset_database("neo4j")

# Build the metagraph
builder.build_metagraph(graph_json)
builder.close()










"""Uncomment the following if you wish to obtain the result for entity discovery and relationship discovery"""

# Discover entities
# entities = LLMAgent.discover_entities(schema)

# print("Entities as below:\n")
# print(json.dumps(entities,indent=2))

# # Discover relationship
# relationship = LLMAgent.discover_relationship(schema,entities)

# print(f"Relationship as below:\n {json.dumps(relationship, indent=2)}")


# extractor.export_to_json(graph_json,"customer_deliveries")
