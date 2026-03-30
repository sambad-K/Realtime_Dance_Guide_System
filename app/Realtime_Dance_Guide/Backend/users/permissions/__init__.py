"""
Permissions package
"""
from .user_permissions import IsOwnerOrReadOnly, IsOwner

__all__ = ['IsOwnerOrReadOnly', 'IsOwner']
