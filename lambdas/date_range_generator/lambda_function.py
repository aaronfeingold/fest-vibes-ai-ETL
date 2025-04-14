"""
Lambda function to generate date ranges for processing
"""

import json
from datetime import datetime, timedelta

from shared_lib.utils import generate_date_range, publish_sns_message


def lambda_handler(event, context):
    try:
        # Get date range from event or use defaults
        start_date = event.get(
            "start_date", (datetime.now() - timedelta(days=14)).isoformat()
        )
        end_date = event.get("end_date", datetime.now().isoformat())

        # Convert string dates to datetime objects
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        # Generate date range
        dates = generate_date_range(start_dt, end_dt)

        # Publish message to SNS for each date
        for date in dates:
            message = {
                "date": date.isoformat(),
                "status": "pending",
                "timestamp": datetime.now().isoformat(),
            }
            publish_sns_message(
                topic_arn="arn:aws:sns:region:account:scraper-trigger", message=message
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Successfully generated {len(dates)} dates",
                    "dates": [d.isoformat() for d in dates],
                }
            ),
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
