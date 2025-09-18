import sqlite3
import os
import json

class DatabaseExtractor:

    def __init__(self):

        pass

    # Database schema extraction
    def extract_schema(self,db_name):

        # Raise error if the database file not found
        if not os.path.exists(db_name):
            raise FileNotFoundError(f"Database not found. Check filename or directory")
        
        schema = {"tables":{},"foreign_keys":[]} # Initialize schema
        con = sqlite3.connect(db_name)
        cursor = con.cursor()

        # Extract tables from database
        cursor.execute("select name from sqlite_master where type='table';")

        # Get the table name 
        # Can add in (if name[0] != "sqlite_sequence" ) if required
        tables = [table_name[0] for table_name in cursor.fetchall()] 

        # Looping all the tables
        for name in tables:
            # Set the name as key in schema dictionary
            schema["tables"][name] = {"columns":[],"primary_key":[]}

            # Retrieve the columns name, type and primary key
            # Table_info return col_id, col_name, type, nt_null, default_value, primary key
            cursor.execute(f"PRAGMA table_info({name})")
            for col in cursor.fetchall():
                schema["tables"][name]["columns"].append(col[1]) # Append column name
                # If pk column not 0, obtain the primary key(s)
                if col[5] != 0:
                    schema["tables"][name]["primary_key"].append(col[1])
            
            # Foreign_key_list return one row for each foreign keys constraint,(a tuple of 8 elements)
            # Refer to https://www.sqlite.org/pragma.html#pragma_foreign_key_list
            cursor.execute(f"PRAGMA foreign_key_list({name})")
            for fkey in cursor.fetchall():
                schema["foreign_keys"].append({
                    "from_table":name, # current table
                    "parent_table":fkey[2], # parent table of fk
                    "from_column":fkey[3], # current fk col name
                    "parent_column":fkey[4] # parent fk col name
                })
        con.close()
        return schema

    # Extract data from all the tables in database
    # Set limit for user to decide how many rows to obtain
    def extract_data(self,db_name,limit=None):

        if not os.path.exists(db_name):
            raise FileNotFoundError(f"Database file not found. Check filename or path")
        
        con = sqlite3.connect(db_name)
        cursor = con.cursor()

        data={}
        
        cursor.execute("select name from sqlite_master where type='table';")
        # Get all the table name
        # Can add in (if name[0] != "sqlite_sequence" ) if required
        tables = [table_name[0] for table_name in cursor.fetchall()]

        for name in tables:
            # Retrieve all rows 
            query = f"select * from {name} "
            # set the limit of row if user defined
            if limit != None:
                query += f"limit {limit}"
            
            cursor.execute(query)

            # Extract column names from cursor description
            cur_desc = cursor.description
            col_names = [desc[0] for desc in cur_desc]
            
            
            data_record = cursor.fetchall()
            data[name] = [dict(zip(col_names,record)) for record in data_record]

        con.close()
        return data
    
    # Extract both schema and data under one roof
    def extract_schema_data(self, db_name, limit=None):

        schema = self.extract_schema(db_name)
        data = self.extract_data(db_name, limit = limit)
        
        return {"schema":schema, "data": data}

    # Export schema / data to JSON format

    def export_to_json(self, content, filename):

        with open(filename,"w") as f:
            json.dump(content,f,indent=4)
        
        print(f"Exported to {filename}")



     











