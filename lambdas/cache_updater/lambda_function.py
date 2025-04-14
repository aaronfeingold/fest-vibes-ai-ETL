"""
Lambda function to update Redis cache with database data
"""

import json
from datetime import datetime, timedelta

from shared_lib.models import CacheEntry
from shared_lib.utils import check_access_level, get_db_client, get_redis_client


def lambda_handler(event, context):
    try:
        # Parse SNS message
        sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
        date = datetime.fromisoformat(sns_message["date"])

        # Get database client
        db_client = get_db_client()

        # TODO: Implement your database query logic here
        # This is where you'd query your PostgreSQL database
        # For example:
        # events = db_client.execute("SELECT * FROM events WHERE date = %s", (date,))

        # Get Redis client
        redis_client = get_redis_client()

        # Update cache with different TTLs based on access level
        for access_level in ["free", "premium"]:
            # Calculate TTL based on access level
            ttl = 86400 if access_level == "free" else 2592000  # 1 day vs 30 days

            # Create cache entry
            cache_entry = CacheEntry(
                key=f"events:{date.isoformat()}:{access_level}",
                value={
                    "events": [],  # Your queried events
                    "date": date.isoformat(),
                    "access_level": access_level,
                },
                ttl=ttl,
                access_level=access_level,
            )

            # Store in Redis
            redis_client.setex(
                cache_entry.key, cache_entry.ttl, json.dumps(cache_entry.value)
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Successfully updated cache for {date.isoformat()}",
                    "access_levels": ["free", "premium"],
                }
            ),
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
