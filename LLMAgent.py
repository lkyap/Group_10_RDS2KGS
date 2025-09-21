"""
Author: Yap, Ashwin, Evanna

Descriptions:
1. Set up OpenAI model
2. Use LLM to extract entity which represents nodes
3. Use LLM to extract relationship based on entity extracted and database schema

"""


import json
from openai import OpenAI
from LLMPrompt import entity_discovery_prompt, relationship_discovery_prompt, graph_entity_prompt

class LLMKGAgent:
    def __init__(self, model = "gpt-5-mini"):
        self.client = OpenAI()
        self.model = model

    def discover_entities(self, schema: dict):
        # Use dictionary to run entity discovery
        schema_str = json.dumps(schema, indent=2)
        response = self.client.chat.completions.create(
            model = self.model,
            messages = [
                {"role":"system","content": entity_discovery_prompt},
                {"role":"user","content": f"Database schema provided:\n {schema_str}"}
            ],
            response_format={"type":"json_object"} # Return JSON format
        )
        
        return json.loads(response.choices[0].message.content)
    
    def discover_relationship(self, schema:dict,entity_config: list[dict]):
        # Discover relationship with schema and entity configuration
        schema_str = json.dumps(schema,indent=2)
        entity_str = json.dumps(entity_config, indent=2)

        response = self.client.chat.completions.create(
            model = self.model,
            messages = [
                {"role":"system","content": relationship_discovery_prompt},
                {"role":"user","content":f"Database schema:\n{schema_str}.\n Entity configuration:\n{entity_str}"}
            ],
            response_format = {"type":"json_object"} # get the response in json format
        )
        
        return json.loads(response.choices[0].message.content)
    
    def generate_kgs(self, schema:dict):
        schema_str = json.dumps(schema, indent=2)
        response = self.client.chat.completions.create(
            model= self.model,
            messages=[
                {"role":"system","content":graph_entity_prompt},
                {"role":"user","content":f"Use schema_str to generate full knowledge graph: \n {schema_str}"}
            ],
            response_format={"type":"json_object"}
        )
        return json.loads(response.choices[0].message.content)
