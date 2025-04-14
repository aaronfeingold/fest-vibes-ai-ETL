"""
Common utility functions used across the ETL pipeline
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any

import boto3
import redis


def get_redis_client() -> redis.Redis:
    """Get Redis client with connection pooling"""
    return redis.Redis(host="your-redis-host", port=6379, db=0, decode_responses=True)


def get_s3_client():
    """Get S3 client with proper configuration"""
    return boto3.client("s3")


def get_db_client():
    """Get PostgreSQL client with connection pooling"""
    # Implementation will depend on your DB setup
    pass


def generate_date_range(start_date: datetime, end_date: datetime) -> list:
    """Generate a list of dates between start and end date"""
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += timedelta(days=1)
    return date_list


def publish_sns_message(topic_arn: str, message: Dict[str, Any]):
    """Publish message to SNS topic"""
    sns = boto3.client("sns")
    sns.publish(TopicArn=topic_arn, Message=json.dumps(message))


def check_access_level(user_id: str) -> str:
    """Check user's access level (free/premium)"""
    # Implementation will depend on your user management system
    return "free"  # Default to free access
