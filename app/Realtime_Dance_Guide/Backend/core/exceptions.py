"""
Custom exceptions for the Dance application
"""


class DanceBaseException(Exception):
    """
    Base exception for all custom exceptions in the application
    """
    default_message = "An error occurred"
    default_code = "error"
    
    def __init__(self, message=None, code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class ValidationException(DanceBaseException):
    """
    Exception for validation errors
    """
    default_message = "Validation failed"
    default_code = "validation_error"


class AuthenticationException(DanceBaseException):
    """
    Exception for authentication errors
    """
    default_message = "Authentication failed"
    default_code = "authentication_error"


class PermissionException(DanceBaseException):
    """
    Exception for permission errors
    """
    default_message = "Permission denied"
    default_code = "permission_error"
