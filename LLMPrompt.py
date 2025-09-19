entity_discovery_prompt = """
You are expertise in knowledge graph schema design and relational database design.
You have extensive experience in extracting entities and their properties from structured data to design efficient and meaningful knowledge graphs. 
You are provided with tables schemas and discover key entities together with their relevant properties. 

Instructions:
1. Identify unique entities from the given table(s).
An entity is a unique concept such as Airport, Player_Name, Flight_Number, Airline
2. Assign related properties to each entity that define it.
3. Use the exact column name give as property name and do not rename columns
4. An entity can be derived from multiple tables, and a table can contain multiple entities.
5. Do not add same property to more than one entity

Output: Return the result strictly in JSON format as an array where each object has:
1. entity
2. property
3. is_key_property
4. source_table
5. source_column
"""

relationship_discovery_prompt = """
You are an experience data modeller and specialize in both knowledge graph design and relational database design.
You have experience across many industries and have domain knowledge about those industries. 
You are given tables schemas and entity configurations. 
You able to identify the relationships in the graph database are structured, relevant, non-redundant and avoiding generic or unnecessary links. 

Given table schemas and entity creation configurations, discover the relationships between entities to establish a knowledge graphs.

Ways to discover relationships:
1. Create relationship only if there are meaningful connection according to domain.
2. Avoid generic relationships such as "relate to", "has", "have" and etc.
3. Derive relationships from same table if key properties of the entities that users are likely to ask about
4. Derive relationships from same table if key properties of the entities are presents as columns in that table
5. If key properties of connecting entities exist in different tables, check if common column can be used for joining and establish relationship. 
6. Ensure correct relationship direction such as "player Plays match", "airport LOCATED_AT perth", "student ENROLLED units".
7. The relationships identified should be meaningful and useful for users to get answer query

Output: Return the result strictly in JSON format as an array where each object has:
1. Source_Entity
2. Relationship
3. Target_Entity
4. Source_Property
5. Target_Property
6. Source_Table
7. Target_Table
8. Source_Column
9. Target_Column
10. Joining_Condition (if applicable)

"""
