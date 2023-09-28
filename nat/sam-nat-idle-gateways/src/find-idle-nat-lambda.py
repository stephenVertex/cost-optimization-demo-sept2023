#!/usr/bin/env python3

import boto3
import time
import requests
import datetime
import json
from secrets_manager import get_secret

def lambda_handler(event, context):


    # Parameters for CUR query
    database  = 'test-adb'
    table     = 'demo_nat_demo_cur'
    s3_output = 's3://sjb-sample-cur/query-results'

    # Athena client
    session = boto3.Session()
    client  = session.client('athena', region_name='us-east-1')

    # Running an Athena query, storing the results in S3
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

    # Query for NAT Gateways
    query = """
    SELECT * FROM "AwsDataCatalog"."test-adb"."demo_nat_demo_cur";
    """

    query = """
    SELECT product_region,
            line_item_usage_account_id,
            line_item_resource_id,
            line_item_line_item_type,
            line_item_usage_start_date, 
            line_item_usage_end_date, 
            line_item_usage_type,
            sum(cost) as cost
     FROM "AwsDataCatalog"."test-adb"."demo_nat_demo_cur"
     WHERE line_item_line_item_type = 'Usage' 
       AND (line_item_usage_type LIKE '%NatGateway-Hours%' OR line_item_usage_type LIKE '%NatGateway-Bytes%')
    GROUP BY 1,2,3,4,5,6,7;
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


    # Query results
    paginator = client.get_paginator('get_query_results')
    row_set = []
    page_num = 1
    for page in paginator.paginate(QueryExecutionId=query_id):
        print(f"{page_num=}")    
        row_set = row_set + page['ResultSet']['Rows']
        page_num = page_num + 1

    # Make the results into one big list
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

    ## Send out a message via SNS?
    sns = session.client('sns', region_name='us-east-1')
    structured_msg = {
        "src" : "stephens-idle-nat-gateway-detector-v0.1.2",
        "dt"  : datetime.datetime.now().isoformat(),
        "idle_gateways" : no_byte_arns    
    }
    sns.publish(
        TopicArn="arn:aws:sns:us-east-1:750813457616:monitoring-and-alerting-develop-SNSTopicAlerting-rFSY91iOcCBu",
        Message=json.dumps(structured_msg),
        Subject="Idle NAT Gateway alert",
    )


    ################################################################################
    ## Let's make a Slack Message
    ## 

    slack_msg = {
        "blocks": [
            {
                "type": "section",
                "block_id": "sectionBlockWithRestaurantImageThaiDescription",
                "text": {
                    "type": "mrkdwn",
                    "text": "Hello there, we have found the following NAT gateways to be idle for the past 31 days"
                }
            },            
        ]
    }

    def mkCheckBox(cb_text, cb_descr, value):
        rval = {
            "text": {
                "type": "mrkdwn",
                "text": cb_text
            },
            "description": {
                "type": "mrkdwn",
                "text": cb_descr
            },
            "value": value
        }
        return(rval)

    slack_msg['blocks'].append(
        {
            "type": "divider"
        }
    )

    checkbox_section = {
        "type": "section",
        "block_id": "sectionBlockWithCheckboxesMrkdwn",
        "text": {
            "type": "mrkdwn",
            "text": "Select to delete"
        },
        "accessory": {
            "type": "checkboxes",
            "options" : []
        }
    }

    cb_options = []
    for arn in no_byte_arns:
        acct = arn.split(":")[4]

        # get region from arn
        region = arn.split(":")[3]


        cb = mkCheckBox(f"*arn:* `{arn}`",
                        f"Acct: {acct}, Region: {region}",
                        arn)
        cb_options.append(cb)
    checkbox_section['accessory']['options'] = cb_options
    slack_msg['blocks'].append(checkbox_section)


    button = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Delete (Exercise for reader)",
                    "emoji": True
                },
                "value": "click_me_123",
                "action_id": "actionId-0"
            }
        ]
    }
    slack_msg['blocks'].append(button)

    ########################################
    ## Store secrets with secrets manager
    secret = get_secret(secret_name="demo/slack_webhook_url")
    shurl = secret["demo/slack_webhook_url"]
    requests.post(url=shurl, json=slack_msg)

    return(json.dumps(structured_msg))
