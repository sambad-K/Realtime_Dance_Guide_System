"""
Utility functions for the Dance application
"""
from typing import Any, Dict
from rest_framework.response import Response
from rest_framework import status


def success_response(data: Any = None, message: str = "Success", status_code: int = status.HTTP_200_OK) -> Response:
    """
    Standardized success response format
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
    
    Returns:
        Response object with standardized format
    """
    response_data = {
        'success': True,
        'message': message,
    }
    
    if data is not None:
        response_data['data'] = data
    
    return Response(response_data, status=status_code)


def error_response(message: str = "Error occurred", errors: Dict = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    """
    Standardized error response format
    
    Args:
        message: Error message
        errors: Detailed errors dictionary
        status_code: HTTP status code
    
    Returns:
        Response object with standardized format
    """
    response_data = {
        'success': False,
        'message': message,
    }
    
    if errors is not None:
        response_data['errors'] = errors
    
    return Response(response_data, status=status_code)


def paginated_response(queryset, serializer_class, request, message: str = "Success"):
    """
    Helper function to create paginated response
    
    Args:
        queryset: Django queryset to paginate
        serializer_class: Serializer class to use
        request: Request object for pagination context
        message: Success message
    
    Returns:
        Response object with paginated data
    """
    from rest_framework.pagination import PageNumberPagination
    
    paginator = PageNumberPagination()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(paginated_queryset, many=True)
    
    return paginator.get_paginated_response({
        'success': True,
        'message': message,
        'data': serializer.data
    })
