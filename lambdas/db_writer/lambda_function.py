"""
Lambda function to write scraped data to the database
"""

import json
from datetime import datetime

from shared_lib.models import EventData
from shared_lib.utils import get_db_client, get_s3_client, publish_sns_message


def lambda_handler(event, context):
    try:
        # Parse SNS message
        sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
        s3_key = sns_message["s3_key"]
        date = datetime.fromisoformat(sns_message["date"])

        # Get data from S3
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket="your-bucket-name", Key=s3_key)
        data = json.loads(response["Body"].read().decode("utf-8"))

        # Get database client
        db_client = get_db_client()

        # TODO: Implement your database writing logic here
        # This is where you'd write to your PostgreSQL database
        # For example:
        # for event in data['events']:
        #     db_client.execute("INSERT INTO events ...")

        # Publish completion message
        message = {
            "date": date.isoformat(),
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "events_processed": len(data.get("events", [])),
                "date": date.isoformat(),
            },
        }
        publish_sns_message(
            topic_arn="arn:aws:sns:region:account:cache-updater-trigger",
            message=message,
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Successfully wrote data to database for {date.isoformat()}",
                    "summary": message["summary"],
                }
            ),
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
