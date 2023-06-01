########
# Instructions:
# 1. Create a CSV with 2 columns in the following order: full_table_id, desired description
#	full_table_id must be lowercase in the format database:schema.table
# 2. Run this script, input your API Key ID, Token (generated in Settings -> API within MC UI)
# 3. Input the Data Warehouse ID in which the tables to import descriptions exist (will check and ignore tables in other warehouses)
#	Note: If you do not know the Data Warehouse ID, you can skip by pressing enter and the script will give you the options to choose from.  You'll need to rerun the script after this.
# 4. Input the name of the CSV with the descriptions
#   Note: If you have a list of descriptions for tables in multiple warehouses, run again for each data warehouse ID
########

from pycarlo.core import Client, Query, Mutation, Session
import csv
import json
from typing import Optional
import requests

mcd_gql_api = "https://api.getmontecarlo.com/graphql"

def getDefaultWarehouse(mcdId,mcdToken):
	client=Client(session=Session(mcd_id=mcdId,mcd_token=mcdToken))
	query=Query()
	query.get_user().account.warehouses.__fields__("name","connection_type","uuid")
	warehouses=client(query).get_user.account.warehouses
	if len(warehouses) == 1:
		return warehouses[0].uuid
	elif len(warehouses) > 1:
		for val in warehouses:
			print("Name: " + val.name + ", Connection Type: " + val.connection_type + ", UUID: " + val.uuid)
		print("Error: More than one warehouse, please re-run with UUID value")
		quit()

def get_table_query(dwId,first: Optional[int] = 1000, after: Optional[str] = None) -> Query:
    query = Query()
    get_tables = query.get_tables(first=first, dw_id=dwId, is_deleted=True, **(dict(after=after) if after else {}))
    get_tables.edges.node.__fields__("full_table_id","mcon")
    get_tables.page_info.__fields__(end_cursor=True)
    get_tables.page_info.__fields__("has_next_page")
    return query

def getMcons(mcdId,mcdToken,dwId):
	client=Client(session=Session(mcd_id=mcdId,mcd_token=mcdToken))
	table_mcon_dict={}
	next_token=None
	while True:
		response = client(get_table_query(dwId=dwId,after=next_token)).get_tables
		for table in response.edges:
			table_mcon_dict[table.node.full_table_id.lower()] = table.node.mcon
		if response.page_info.has_next_page:
			next_token = response.page_info.end_cursor
		else:
			break
	return table_mcon_dict

def getHeaders(mcdId, mcdToken):
	return {
		'Content-Type': 'application/json',
		'x-mcd-id': mcdId,
		'x-mcd-token': mcdToken
	}

def getPayload(query, variables):
	data = {
		'query': query,
		'variables': variables
	}
	payload = json.dumps(data, ensure_ascii=False).replace("\\\\", "\\")

	return payload

def importDescriptionsFromCSV(mcdId,mcdToken,csvFileName, mconDict):
	description_update_query = """
		mutation createOrUpdateCatalogObjectMetadata($mcon: String!, $description: String!) {
            createOrUpdateCatalogObjectMetadata(mcon: $mcon, description: $description) {
                catalogObjectMetadata {
                    mcon
                }
              }
            }
		"""

	headers = getHeaders(mcdId, mcdToken)

	with open(csvFileName,"r") as descriptions_to_import:
		descriptions=csv.reader(descriptions_to_import, delimiter=",")
		total_desc=0
		imported_desc_counter = 0
		for row in descriptions:
			total_desc += 1
			if row[0].lower() not in mconDict.keys():
				print("check failed: " + row[0].lower())
				continue
			if mconDict[row[0].lower()]:
				print("check succeeded: " + row[0].lower())

				query_variables = {
					"mcon": mconDict[row[0].lower()],
					"description": row[1]
				}

				payload = getPayload(description_update_query, query_variables)

				response = requests.post(mcd_gql_api, data=payload, headers=headers)
				print(response.text)

				imported_desc_counter += 1

	print("Successfully Imported " + str(imported_desc_counter) + " of " + str(total_desc) + " Table Descriptions")

if __name__ == '__main__':
	#-------------------INPUT VARIABLES---------------------
	mcd_id = input("MCD ID: ")
	mcd_token = input("MCD Token: ")
	dw_id = input("DW ID: ")
	csv_file = input("CSV Filename: ")
	#-------------------------------------------------------
	if dw_id and csv_file:
		mcon_dict = getMcons(mcd_id,mcd_token,dw_id)
		importDescriptionsFromCSV(mcd_id,mcd_token,csv_file,mcon_dict)
	elif csv_file and not dw_id:
		warehouse_id = getDefaultWarehouse(mcd_id,mcd_token)
		mcon_dict = getMcons(mcd_id,mcd_token,warehouse_id)
		importDescriptionsFromCSV(mcd_id,mcd_token,csv_file,mcon_dict)
