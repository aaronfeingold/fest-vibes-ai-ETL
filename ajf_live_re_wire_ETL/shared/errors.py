"""
Error handling for the application.
"""

from enum import Enum


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


class ScrapingError(Exception):
    """Custom exception for DeepScraper errors."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.GENERAL_ERROR,
        status_code: int = 500,
    ):
        """
        Initialize a ScrapingError.

        Args:
            message (str): A human-readable error message.
            error_type (ErrorType): The category of the error (default: GENERAL_ERROR).
            status_code (int): HTTP-style status code associated with the error (default: 500).
        """
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)


class DatabaseHandlerError(Exception):
    """Custom exception for when the Database Handler errors."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.DATABASE_ERROR,
        status_code: int = 500,
    ):
        """
        Initialize a DatabaseHandlerError.

        Args:
            message (str): A human-readable error message.
            error_type (ErrorType): The category of the error (default: DATABASE_ERROR).
            status_code (int): HTTP-style status code associated with the error (default: 500).
        """
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)
