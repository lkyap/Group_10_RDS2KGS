"""
Author: Yap

How to run:
1. Set your API key in the local environment.
    - If you are using VSCode, under the terminal, set the OPENAI API Key by typing "$env:OPENAI_API_KEY = 'Replace API KEY HERE'"
2. After setting up the API key, you should be running it without error.
3. Otherwise, check your working directory is correctly set up.

Overview / descriptions:
1. Set up working directory and directory for the respective output files
2. Extract Relational Database schema and data, then store in JSON file
3. Send the extracted RDS schema to LLM for Knowledge Graph Schema generation
4. Create a JSON file and write the return Knowledge Graph Schema in created JSON file
"""

# Library and functions
from SchemaDataExtractor import DatabaseExtractor
from LLMAgent import LLMKGAgent
import json
import os
from GraphCreation import GraphCreation
from kgscreate import MetaGraphBuilder
import DataMapping
from pathlib import Path
from dotenv import load_dotenv
from schema_relationship_eval import Schema_Evaluation,Relationship_Evaluation
import csv


'''
Section 1: Set up database directory / database file name

Instructions:
- Replace the "db_dataset" if the database folder is different
- Rename the folder name if needed
'''

# Set database directory and get the list of database in the folder
db_folder_path =  Path("db_dataset")
db_files_list = [file for file in db_folder_path.glob("*.sqlite")]

# Set directory for extracted schema and data from RDS
rds_schema_dir = Path("extracted_output/rds_schema")
rds_data_dir = Path("extracted_output/rds_data")

rds_schema_dir.mkdir(parents=True,exist_ok=True)
rds_data_dir.mkdir(parents=True,exist_ok=True)

# Set directory for Knowledge Graph schema return from LLM
kgs_schema_dir = Path("kgs_schema_generated")
kgs_schema_dir.mkdir(parents=True,exist_ok=True)

# Set directory for Knowledge Graph data by mapping extracted
kgs_data_dir = Path("kgs_data_generated")
kgs_data_dir.mkdir(parents=True,exist_ok=True)

# Set directory for the evaluation result for showing in 
csv_eval_dir = Path("evaluation_summary")
csv_eval_dir.mkdir(parents=True,exist_ok=True)

'''
Section 2: Relational database schema and data extraction

Descriptions:
1. Extract the relational database schema 
2. Create JSON file for the extracted schemas and data
3. Write the extracted schema and data in the JSON file.
4. Send the extracted relational database schema to LLM through API 
5. Store the knowledge graph schema return by LLM 

'''
# Initialize agent and model
load_dotenv("cred.env")
api_key = os.getenv("OPENAI_API_KEY")

# Get the API key and set the model we wish to use from OpenAI
LLMAgent = LLMKGAgent(api_key=api_key,model="gpt-5-mini")

# Initialize variable for Evaluation Result

all_db_eval_summary = []

# Loop through the database in the folder
for db in db_files_list:
    try:
        # Extract the relational database schema and store in JSON file 
        extractor = DatabaseExtractor()
        schema = extractor.extract_schema(str(db))
        schema_json= rds_schema_dir / f"{db.stem}_schema.json"
        with open(schema_json,"w",encoding="utf-8") as f:
            json.dump(schema,f,indent=2)
        print(schema)
        print("\n")
        print(f"{db.name} schema extracted successfully.\n")

        # Extract the relational database data and store in JSON file
        data = extractor.extract_data(str(db))
        data_json = rds_data_dir / f"{db.stem}_data.json"
        with open(data_json,"w",encoding="utf-8") as f:
            json.dump(data,f,indent=2)
        print(data)
        print("\n")
        print(f"{db.name} data extracted successfully.\n")

        '''
        Section 3: Generate knowledge graph

        Descriptions
        1. Send the extracted RDS schema to LLM
        2. Create a JSON file
        3. Write the Knowledge Graph Schema into the created JSON file
        '''

        # Get the LLM to generate the knowledge graph schema
        graph_json = LLMAgent.generate_kgs(schema)

        # Create a JSON file and write in the schema generated
        kgs_schema_file = kgs_schema_dir / f"{db.stem}_kgs.json"

        with open(kgs_schema_file,"w",encoding="utf-8") as f:
            json.dump(graph_json,f,indent=2)
        
        print(f"KGS for {db.name} is created by LLM")

        # Create nodes based on the KGS schema return by LLM
        kgs_data = DataMapping.rds_kgs_data(rds_data=data,kgs_schema=graph_json)

        # Create JSON file
        kgs_data_file = kgs_data_dir / f"{db.stem}_kgs_data.json"

        # Write in the JSON KGS data
        with open(kgs_data_file,"w",encoding="utf-8") as f:
            json.dump(kgs_data,f,indent=2)

        print(f"KGS data of {db.name} created successfully")


        """
        Section 4: Evaluation - Schema Completeness and Relationship Completeness

        Descriptions:

        1. Schema Completeness - Measure the records in an entity with total nodes created in KGS
        2. Relationship Completeness - Measure the records of an entity that has relationship with another entity 
        
        """

        # Schema completeness
        schema_eval = Schema_Evaluation(rds_data_file = data_json,kgs_data_file= kgs_data_file)
        schema_eval_result = schema_eval.eval_schema_complete()

        # Relationship completeness
        rel_eval = Relationship_Evaluation(rds_schema_file=schema_json,rds_data_file=data_json,kgs_data_file=kgs_data_file)
        rel_eval_result =  rel_eval.eval_relationship_complete()

        # Summary result for a DB
        db_eval_summary = {
            "DB_Name":db.stem,
            # Return empty dict and 0 if no result found
            "Schema_Comp": schema_eval_result.get("Schema_Comp_DB",{}).get("SC",0),
            "Relationship_Comp": rel_eval_result.get("RC_DB",{}).get("RC_DB",0)
        }

        print(f"Summary of evaluation on {db.stem}:\n{db_eval_summary}")

        # Append each of the DB evaluation result into a list
        all_db_eval_summary.append(db_eval_summary)

    # Return error
    except Exception as exp_error:
        print(f"Error in processing {db.name}:{exp_error}")

# Create a CSV file
eval_csv_file = csv_eval_dir / f"evaluation_summary.csv"

# Write the CSV file with the summary result
with open(eval_csv_file,"w",newline="",encoding="utf-8") as f:
    writer = csv.DictWriter(f,fieldnames = ["DB_Name","Schema_Comp","Relationship_Comp"])
    writer.writeheader()
    writer.writerows(all_db_eval_summary)

print("\nEvaluation summary saved into {eval_csv_file}")


'''
The following is to build the metagraph on Neo4j. 

Purpose: Compare the Neo4j and yFiles to see which is more user friendly
'''


# # Build metagraph
# builder = MetaGraphBuilder("bolt://localhost:7687", "neo4j", "CapstoneProject@1234")

# # Clean database before creating
# builder.reset_database("neo4j")

# # Build the metagraph
# builder.build_metagraph(graph_json)
# builder.close()

# show_data = DataMapping.map_relational_data_to_graph_format(graph_json,data)
# extractor.export_to_json(show_data,"swimming_data")
# print(show_data)


"""
The following is the improvement plan for the future:
# Note: Reference from: https://medium.com/@pallavisinha12/ai-driven-knowledge-graph-schema-discovery-concept-and-implementation-50843bb90fbb

1. Instead of getting LLM to return the nodes and edges from the relational database schema, we get LLM to return the knowledge graph discovery
2. From the knowledge graph discovery and dimension modelling, expert or relevant users would be able to do the checking in real life application
3. From the schema discovered, create the entity and relationships in form of metagraph and load the data to create nodes and relationships between them.
"""


"""Uncomment the following if you wish to obtain the result for entity discovery and relationship"""

# Discover entities

entities = LLMAgent.discover_entities(graph_json)

print("Entities as below:/n")
print(json.dumps(entities,indent=2))

# Discover relationship
relationship = LLMAgent.discover_relationship(graph_json,entities)

print(f"Relationship as below:/n {json.dumps(relationship, indent=2)}")



