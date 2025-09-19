"""
Author: Yap

Descriptions:
1. Set your API key in the local environment.
    - If you are using VSCode, under the terminal, write 
"""



from SchemaDataExtractor import DatabaseExtractor
from LLMAgent import LLMKGAgent
import json
import os


extractor = DatabaseExtractor()
schema = extractor.extract_schema("C:/Users/ewa_c/lkyap/UWA - Master DS Course Units/S2-2025/Project/spider_data/spider_data/database/flight_company/flight_company.sqlite")
print(schema)
print("\n")

# Initialize agent and model
LLMAgent = LLMKGAgent(model="gpt-5-mini")

# Discover entities
entities = LLMAgent.discover_entities(schema)
print("Entities as below:\n")
print(json.dumps(entities,indent=2))

# Discover relationship
relationship = LLMAgent.discover_relationship(schema,entities)
print(f"Relationship as below:\n {json.dumps(relationship, indent=2)}")



