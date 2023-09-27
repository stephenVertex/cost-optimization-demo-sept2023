#!/usr/bin/env python3

import boto3
import time

# Query definitions
database = 'test-adb'
table = 'demo_nat_demo_cur'
s3_output = 's3://sjb-sample-cur/query-results'

# Athena client
session = boto3.Session(profile_name='ab')
client = session.client('athena', region_name='us-east-1')


def run_query(query, database, s3_output):
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            'Database': database
        },
        ResultConfiguration={
            'OutputLocation': s3_output,
        }
    )
    print('Execution ID: ' + response['QueryExecutionId'])
    return response['QueryExecutionId']

# Query to find the table size
query = """
SELECT * FROM "AwsDataCatalog"."test-adb"."demo_nat_demo_cur";
"""
query_id = run_query(query, database, s3_output)

# Wait for the query to finish
while True:
    stats = client.get_query_execution(QueryExecutionId=query_id)
    status = stats['QueryExecution']['Status']['State']

    if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        print(stats['QueryExecution']['Status'])
        break

    time.sleep(5)  # wait 5 seconds before checking again


# results = client.get_query_results(QueryExecutionId=query_id)

# Query results
paginator = client.get_paginator('get_query_results')
row_set = []
page_num = 1
for page in paginator.paginate(QueryExecutionId=query_id):
    print(f"{page_num=}")    
    row_set = row_set + page['ResultSet']['Rows']
    page_num = page_num + 1

header = [col['VarCharValue'] for col in row_set[0]['Data']]
data_rows = [{header[i]: col['VarCharValue'] for i, col in enumerate(row['Data'])} for row in row_set[1:]]    

## Give me a set of distinct arns in this set
unique_arns = set([x['line_item_resource_id'] for x in data_rows])
unique_usage_types = set([x['line_item_usage_type'] for x in data_rows])

no_byte_arns = []

for arn in unique_arns:
    num_bytes = 0
    dr = list(filter(lambda x: x['line_item_resource_id'] == arn and "Bytes" in x['line_item_usage_type'], data_rows))
    if len(dr) == 0:
        no_byte_arns.append(arn)

        
print("No byte arns:")
print(no_byte_arns)
      
print("We should probably get rid of these")
