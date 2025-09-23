"""
Author: Yap

Description:
1. Build metagraph from the result of LLM

"""


from neo4j import GraphDatabase

class MetaGraphBuilder:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def build_nodes(self, nodes):
        """Create meta-graph nodes (Entity level)."""
        with self.driver.session() as session:
            for node in nodes:

                cypher = """MERGE (n:Entity {name: $name}) SET n.key = $key, n.properties = $properties"""
                session.run(cypher,name=node["id"],key=node["key"],properties=node["properties"])

    def build_edges(self, edges):
        """Create meta-graph edges (Relationships between entities)."""
        with self.driver.session() as session:
            for edge in edges:
                rel_type = edge["relationship"]
                cypher = f"""
                MATCH (a:Entity {{name:$source}}), (b:Entity {{name:$target}})
                MERGE (a)-[:{rel_type} {{
                    source_column:$scol, target_column:$tcol
                }}]->(b)"""

                session.run(cypher, source=edge["source"], target=edge["target"],
                     scol=edge["source_column"], tcol=edge["target_column"])
    
    def reset_database(self,db_name="neo4j"):
        with self.driver.session(database=db_name) as session:
            session.run("MATCH (n) DETACH DELETE n")

    def build_metagraph(self, schema_json):
        """Builds the full meta-graph from schema JSON."""
        self.build_nodes(schema_json["nodes"])
        self.build_edges(schema_json["edges"])
