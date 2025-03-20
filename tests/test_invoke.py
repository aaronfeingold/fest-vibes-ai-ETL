import json
import asyncio
from main import lambda_handler


# Simulated AWS Lambda context
class LambdaTestContext:
    aws_request_id = "test-request-id"
    log_stream_name = "test-log-stream"
    function_name = "test-function"
    function_version = "1.0"
    memory_limit_in_mb = 128
    invoked_function_arn = (
        "arn:aws:lambda:us-west-2:123456789012:function:test-function"
    )
    remaining_time_in_millis = 30000  # Simulated remaining time


# Simulated event data
event = {
    "queryStringParameters": {"date": "2025-03-20"},
    "httpMethod": "POST",
    "devEnv": False,
}


# Invoke the handler and print the result
async def test_lambda_handler():
    result = await lambda_handler(event, LambdaTestContext())
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    asyncio.run(test_lambda_handler())
