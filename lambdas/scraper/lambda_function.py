"""
Lambda function to scrape event data
"""

import json
from datetime import datetime

from shared_lib.models import EventData
from shared_lib.utils import get_s3_client, publish_sns_message


def lambda_handler(event, context):
    try:
        # Parse SNS message
        sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
        date = datetime.fromisoformat(sns_message["date"])

        # TODO: Implement your scraping logic here
        # This is where you'd use your existing scraping code
        scraped_data = {"date": date.isoformat(), "events": []}  # Your scraped events

        # Upload to S3
        s3_client = get_s3_client()
        s3_key = f'raw_data/{date.strftime("%Y-%m-%d")}.json'
        s3_client.put_object(
            Bucket="your-bucket-name", Key=s3_key, Body=json.dumps(scraped_data)
        )

        # Publish completion message
        message = {
            "s3_key": s3_key,
            "date": date.isoformat(),
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
        }
        publish_sns_message(
            topic_arn="arn:aws:sns:region:account:db-writer-trigger", message=message
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Successfully scraped and uploaded data for {date.isoformat()}",
                    "s3_key": s3_key,
                }
            ),
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
