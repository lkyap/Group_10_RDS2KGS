"""
Author: Yap, Ashwin, Evanna

Descriptions:
1. Set up OpenAI model
2. Pass in the extracted RDS schema and use LLM to generate the KGS schema

Improvement plan:
1. Use LLM to extract entity which represents nodes
2. Use LLM to extract relationship based on entity extracted and database schema
3. The extracted entity and relationship should be evaluated by expert before using it
4. If the extracted entity and relationship are satisfied by user, generate the Knowledge Graph based on the entity and relationship

"""


import json
from openai import OpenAI
from LLMPrompt import entity_discovery_prompt, relationship_discovery_prompt, graph_entity_prompt

class LLMKGAgent:
    def __init__(self,api_key ,model = "gpt-5-mini"):
        self.client = OpenAI(api_key = api_key)
        self.model = model

    # This is for entities discovery which is on the improvement plan
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
    
    # This is for relationship discovery which is on the improvement plan
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
    
    # Use RDS Schema to generate Knowledge Graph schema by using LLM
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


