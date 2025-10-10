"""
Author: Yap

Descriptions:
1. The function in this script is to map the RDS data into Knowledge Graph data

Steps:
1. From the graph schema, map between the nodes and table
2. From the graph schema, map between the source(parent) table, target table, and relationship
3. Map the properties for the nodes from source table and target table 
"""

def rds_kgs_data(rds_data,kgs_schema):

    graph = {"nodes": [], "edges": []}

    # Create nodes for each of the record in the table
    for node_schema in kgs_schema["nodes"]:
        label = node_schema["id"] # Label for the nodes. Example: "Cinema","Flight"

        rds_record = rds_data.get(label,[])

        for index, row in enumerate(rds_record):
            node_id = f"{label}_{index}" # Create unique node id for each node

            graph["nodes"].append({
                "id": node_id, # Assign node id
                "label": label, # Assign label
                "properties": row # Insert columns information into properties
            })

    for edges in kgs_schema["edges"]:
        
        source_label = edges["source"] # From node
        target_label = edges["target"] # To node

        # Mapping relationship from source node to target node
        source_column = edges["source_column"] 
        target_column = edges["target_column"]

        # Get the relationship
        rel_type = edges.get("relationship","related_to") # If no relationship found, set default value to "related_to"

        # Set up lookup dictionary
        target_index = {}

        for index, row in enumerate(rds_data.get(target_label)):
            # If the column exist in the record
            if target_column in row:
                target_index[row[target_column]] = f"{target_label}_{index}" # target_node_id

        for index, source_row in enumerate(rds_data.get(source_label,[])):
            
            # Skip the record if source column does not exist
            if source_column not in source_row:
                continue
            
            # Get the value from the source column record
            source_value = source_row[source_column]

            target_id = target_index.get(source_value)

            if not target_id:
                continue

            source_id = f"{source_label}_{index}"

            graph["edges"].append({
            "source":source_id,
            "target": target_id,
            "relationship": rel_type
            })
    return graph



    








