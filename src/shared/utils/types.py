from enum import Enum
from typing import Any, Dict, TypedDict, Union


class ErrorType(Enum):
    """
    Enumeration for various error types used in the application.

    Attributes:
        GENERAL_ERROR: Represents a general error that does not fall into specific categories.
        HTTP_ERROR: Represents an error related to HTTP requests.
        URL_ERROR: Represents an error related to malformed or inaccessible URLs.
        FETCH_ERROR: Represents an error that occurs during data fetching.
        NO_EVENTS: Represents a situation where no events are found.
        PARSE_ERROR: Represents an error that occurs during data parsing.
        SOUP_ERROR: Represents an error related to BeautifulSoup operations.
        UNKNOWN_ERROR: Represents an unknown or unspecified error.
        AWS_ERROR: Represents an error related to AWS services.
        VALUE_ERROR: Represents an error caused by invalid values.
        DATABASE_ERROR: Represents an error related to database operations.
        GOOGLE_MAPS_API_ERROR: Represents an error related to Google Maps API usage.
        S3_ERROR: Represents an error related to S3 operations.
        REDIS_ERROR: Represents an error related to Redis operations.
        VALIDATION_ERROR: Represents an error related to data validation failures.
    """

    GENERAL_ERROR = "GENERAL_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    URL_ERROR = "URL_ERROR"
    FETCH_ERROR = "FETCH_ERROR"
    NO_EVENTS = "NO_EVENTS"
    PARSE_ERROR = "PARSE_ERROR"
    SOUP_ERROR = "SOUP_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    AWS_ERROR = "AWS_ERROR"
    VALUE_ERROR = "VALUE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    GOOGLE_MAPS_API_ERROR = "GOOGLE_MAPS_API_ERROR"
    S3_ERROR = "S3_ERROR"
    REDIS_ERROR = "REDIS_ERROR"


class LambdaContext:
    """
    A class representing the context object provided to AWS Lambda functions.

    Attributes:
        aws_request_id (str): The unique identifier for the current invocation
            of the Lambda function.
        log_stream_name (str): The name of the CloudWatch log stream for the
            current invocation.
        function_name (str): The name of the Lambda function being executed.
        function_version (str): The version of the Lambda function being
            executed.
        memory_limit_in_mb (int): The amount of memory allocated to the Lambda
            function, in megabytes.
        invoked_function_arn (str): The Amazon Resource Name (ARN) of the Lambda
            function being invoked.
        remaining_time_in_millis (int): The amount of time, in milliseconds,
            remaining before the Lambda function times out.
    """

    aws_request_id: str
    log_stream_name: str
    function_name: str
    function_version: str
    memory_limit_in_mb: int
    invoked_function_arn: str
    remaining_time_in_millis: int


class AwsInfo(TypedDict):
    """
    A TypedDict representing AWS-related information.

    Attributes:
        aws_request_id (str): The unique identifier for the AWS request.
        log_stream_name (str): The name of the log stream associated with the AWS request.
    """

    aws_request_id: str
    log_stream_name: str


class SuccessResponseBase(TypedDict):
    """
    A base class for representing a successful response.

    Attributes:
        status (str): The status of the response, typically indicating success.
        data (Any): The data payload of the response.
        date (str): The date when the response was generated.
    """

    status: str
    data: Any
    date: str


class ErrorResponseBase(TypedDict):
    """
    A TypedDict representing the structure of an error response.

    Attributes:
        status (str): The status of the response, typically indicating failure.
        error (Dict[str, str]): A dictionary containing error details,
        where the key is the error field
        and the value is the corresponding error message.
    """

    status: str
    error: Dict[str, str]


# Define the response types
SuccessResponse = Union[SuccessResponseBase, AwsInfo]
ErrorResponse = Union[ErrorResponseBase, AwsInfo]
ResponseBody = Union[SuccessResponse, ErrorResponse]


class ResponseType(TypedDict):
    """
    ResponseType is a TypedDict that defines the structure of a response object.

    Attributes:
        statusCode (int): The HTTP status code of the response.
        headers (Dict[str, str]): A dictionary containing the headers of the response.
        body (ResponseBody): The body of the response, represented by a ResponseBody object.
    """

    statusCode: int
    headers: Dict[str, str]
    body: ResponseBody
