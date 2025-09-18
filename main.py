from SchemaDataExtractor import DatabaseExtractor

extractor = DatabaseExtractor()
schema = extractor.extract_schema("flight_company.sqlite")
print(schema)
print("\n")

data = extractor.extract_data("flight_company/flight_company.sqlite")
print(data)
print("\n")

schema_data = extractor.extract_schema_data("flight_company.sqlite")
print(schema_data)
print("\n")

print(schema_data["schema"])
print("\n")

print(schema_data["data"])


# Export to JSON
extractor.export_to_json(schema_data,"airport_SchemaData")