"""
Error handling for the application.
"""

from shared.utils.types import ErrorType


class ScrapingError(Exception):
    """Custom exception for DeepScraper errors.

    Common status codes:
    - 502: Bad Gateway (default) - External website issues
    - 404: Not Found - Page doesn't exist
    - 403: Forbidden - Access denied
    - 429: Too Many Requests - Rate limiting
    """

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.GENERAL_ERROR,
        status_code: int = 502,
    ):
        """
        Initialize a ScrapingError.

        Args:
            message (str): A human-readable error message.
            error_type (ErrorType): The category of the error (default: GENERAL_ERROR).
            status_code (int): HTTP-style status code associated with the error (default: 502).
        """
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)


class DatabaseError(Exception):
    """Custom exception for when the Database Handler errors.

    Common status codes:
    - 503: Service Unavailable (default) - Database is down or unreachable
    - 400: Bad Request - Invalid query or parameters
    - 409: Conflict - Constraint violation
    """

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.DATABASE_ERROR,
        status_code: int = 503,
    ):
        """
        Initialize a DatabaseHandlerError.

        Args:
            message (str): A human-readable error message.
            error_type (ErrorType): The category of the error (default: DATABASE_ERROR).
            status_code (int): HTTP-style status code associated with the error (default: 503).
        """
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)


class S3Error(Exception):
    """Custom exception for S3 errors.

    Common status codes:
    - 503: Service Unavailable (default) - S3 service is down or unreachable
    - 404: Not Found - File doesn't exist
    - 403: Forbidden - No permission to access
    - 400: Bad Request - Invalid request parameters
    """

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.S3_ERROR,
        status_code: int = 503,
    ):
        """
        Initialize a S3Error.

        Args:
            message (str): A human-readable error message.
            error_type (ErrorType): The category of the error (default: S3_ERROR).
            status_code (int): HTTP-style status code associated with the error (default: 503).
        """
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)


class RedisError(Exception):
    """Custom exception for Redis errors.

    Common status codes:
    - 503: Service Unavailable (default) - Redis service is down or unreachable
    """

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.REDIS_ERROR,
        status_code: int = 503,
    ):
        """
        Initialize a RedisError.

        Args:
            message (str): A human-readable error message.
            error_type (ErrorType): The category of the error (default: REDIS_ERROR).
            status_code (int): HTTP-style status code associated with the error (default: 503).
        """
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)
