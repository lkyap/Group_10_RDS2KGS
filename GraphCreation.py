"""
Author: Yap
Description:
- Create Neo4j graph from entity/relationship configs and relational data.
"""

from neo4j import GraphDatabase

class GraphCreation:
    def __init__(self, uri: str, username: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    # --------------------------
    # Create entity nodes with data
    # --------------------------
    def create_entities_data(self, entities: list[dict], data: dict):
        with self.driver.session() as session:
            for ent in entities:
                label = ent["entity"]
                table = ent["source_table"]
                column = ent["source_column"]
                is_key = ent["is_key_property"]

                if table not in data:
                    continue

                for record in data[table]:
                    if column not in record:
                        continue

                    if is_key:
                        # MERGE node on key property
                        merge_cypher = f"MERGE (n:{label} {{ {column}: $key_val }})"

                        # Add other properties
                        set_clauses = [f"n.{k} = ${k}" for k in record.keys() if k != column]
                        if set_clauses:
                            cypher = merge_cypher + " SET " + ", ".join(set_clauses)
                        else:
                            cypher = merge_cypher

                        params = {"key_val": record[column]}
                        params.update(record)

                        session.run(cypher, params)

    # --------------------------
    # Create relationships with data
    # --------------------------
    def create_relationships_data(self, relationships: list[dict], data: dict):
        with self.driver.session() as session:
            for rel in relationships:
                source_entity = rel["Source_Entity"]
                target_entity = rel["Target_Entity"]
                source_table = rel["Source_Table"]
                target_table = rel["Target_Table"]
                source_col = rel["Source_Column"]
                target_col = rel["Target_Column"]
                rel_type = rel["Relationship"]

                if source_table not in data or target_table not in data:
                    continue

                for source_data in data[source_table]:
                    for target_data in data[target_table]:
                        if (
                            source_col in source_data
                            and target_col in target_data
                            and source_data[source_col] == target_data[target_col]
                        ):
                            cypher = (
                                f"MATCH (a:{source_entity}), (b:{target_entity}) "
                                f"WHERE a.{source_col} = $source_val "
                                f"AND b.{target_col} = $target_val "
                                f"MERGE (a)-[:{rel_type}]->(b)"
                            )

                            session.run(
                                cypher,
                                source_val=source_data[source_col],
                                target_val=target_data[target_col],
                            )

    # --------------------------
    # Run full graph build
    # --------------------------
    def create_graph(self, entities: list[dict], relationships: list[dict], data: dict):
        self.create_entities_data(entities, data)
        self.create_relationships_data(relationships, data)
