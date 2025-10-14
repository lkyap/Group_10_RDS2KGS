"""
Author: Yap

Descriptions:

1. Evaluate the conversion of the RDS to KGS by using Schema Completeness and Relationship Completeness
2. Schema Completeness (SC): Compare between number of records of an Entity in Relational Database (RDS) and number of nodes in KGS
3. Relationship Completeness (RC): Compare number of records of an Entity in RDS that has relationship with another entity against number of edges between nodes that represent these entities

Note:

1. The definition of SC and RC used was referenced from the paper "An Automated Graph Construction Approach from Relational Databases to Neo4j", https://ieeexplore.ieee.org/document/10029438

"""
# Libary
import json
from collections import Counter

# Schema evaluation class

class Schema_Evaluation:
    def __init__(self, rds_data_file, kgs_data_file):

        self.rds_data = self.load_json(rds_data_file)
        self.kgs_data= self.load_json(kgs_data_file)

    # Load JSON file
    def load_json(self, filepath):
        with open(filepath,"r") as f:
            return json.load(f)
    
    # Count the number of rows in RDS for an entity
    def count_rds_record(self):
        rds_record_count = {table:len(records) for table, records in self.rds_data.items()}
        return rds_record_count
    
    # Count the nodes in the KGS created for each unique label
    def count_kgs_nodes(self):
        kgs_nodes_count = Counter(node["label"] for node in self.kgs_data.get("nodes",[]))
        return kgs_nodes_count

    def eval_schema_complete(self):

        rds_record_count = self.count_rds_record()
        kgs_nodes_count = self.count_kgs_nodes()

        # Initialize dict for final table
        schema_comp_table = {}

        for table,rds_count in rds_record_count.items():
            node_count = kgs_nodes_count.get(table,0)
            
            # SC(T_{i}) = n(N{i}) / n(A_{i})
            # n(N{i}): Set of nodes of graph G for corresponding relational entity
            # n(A_{i}): Set of records A for an entity T_{i} of the schema S
            schema_comp = (node_count / rds_count) if rds_count>0 else 0

            # Store the SC result in dictionary
            schema_comp_table[table] = {
                "RDS_Record": rds_count,
                "KG_Nodes": node_count,
                "SC": round(schema_comp,3)
            }
        
        # Overall SC = sum(SC_{T_i}) / sum(T_i)
        if schema_comp_table:
            schema_comp_final = sum(sce["SC"] for sce in schema_comp_table.values()) / len(schema_comp_table)
        else:
            schema_comp_final = 0

        schema_comp_table["Schema_Comp_DB"] = {"RDS_record":"-","KG_Nodes":"-","SC":round(schema_comp_final,3)}

        return schema_comp_table

# Relationship completeness evaluation
class Relationship_Evaluation:

    def __init__(self,rds_schema_file, rds_data_file,kgs_data_file):
        self.rds_schema = self.load_json(rds_schema_file)
        self.rds_data = self.load_json(rds_data_file)
        self.kgs_data = self.load_json(kgs_data_file)

    # Load JSON file
    def load_json(self,filepath):
        with open(filepath,"r") as f:
            return json.load(f)

    # Evaluate Relationship Completeness
    def eval_relationship_complete(self):
        rc_result = {}
        
        total_actual_node, total_expected_node = 0,0

        # Loop through the foreign key list in RDS Schema
        for fk_list in self.rds_schema.get("foreign_keys",[]):

            # Initiate variables on child_table, parent_table, child_column and parent_column
            child_tab = fk_list["from_table"]
            parent_tab = fk_list["parent_table"]
            child_col = fk_list["from_column"]
            parent_col = fk_list["parent_column"]

            # Get the set of the value in parent column
            parent_val = {record[parent_col] for record in self.rds_data.get(parent_tab,[]) if parent_col in record}

            # Add up the node if the child column is in data and the value of the child column is not missing and child value in list of parent value
            expected_node = sum(1 for record in self.rds_data.get(child_tab,[]) if child_col in record and record[child_col] is not None and record[child_col] in parent_val)

            # Null FK in child table
            null_count = sum(1 for record in self.rds_data.get(child_tab,[]) if child_col in record and record[child_col] is None)

            # Actual edges in KGS
            # Count the edge if the either direction
            actual_node = sum(1 for edge in self.kgs_data["edges"] if (edge["source"].startswith(child_tab) and edge["target"].startswith(parent_tab)) or (edge["target"].startswith(child_tab) and edge["source"].startswith(parent_tab)) )
            
            # Accumulate the counting of expected node and actual node
            total_expected_node += expected_node
            total_actual_node += actual_node

            # Store the result in dictionary
            rc_result[f"{parent_tab}_{child_tab}"] = {
                "Expected_Node":expected_node,
                "Actual_Node": actual_node,
                "Null_FK": null_count,
                # Set as 0 to avoid division zero
                "RC": round((actual_node/expected_node),3) if expected_node > 0  else 0
            }

        # If denominator 0, set as 0 to avoid division zero error
        rc_db = round((total_actual_node/total_expected_node),3) if total_expected_node >0 else 0

        # Add in the overall evaluation on entire DB
        rc_result["RC_DB"] = {
            "Total_Expected_Node":total_expected_node,
            "Total_Actual_Node": total_actual_node,
            "RC_DB": rc_db # Relationship completeness for entire DB
        }

        return rc_result
