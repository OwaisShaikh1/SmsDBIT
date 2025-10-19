"""
Authentication utilities for frontend views that need to work with both
JWT tokens (from API) and Django sessions.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


def get_user_from_request(request):
    """
    Try to get authenticated user from either:
    1. Django session (request.user)
    2. JWT token in Authorization header
    3. JWT token in cookies (accessToken)
    
    Returns (user, auth_method) or (None, None)
    """
    
    # First try Django session auth
    if hasattr(request, 'user') and request.user.is_authenticated:
        return request.user, 'session'
    
    # Then try JWT from Authorization header
    jwt_auth = JWTAuthentication()
    try:
        auth_result = jwt_auth.authenticate(request)
        if auth_result:
            user, token = auth_result
            return user, 'jwt_header'
    except (InvalidToken, TokenError):
        pass
    
    # Finally try JWT from cookies or localStorage (frontend should set this)
    access_token = None
    
    # Check cookies first
    access_token = request.COOKIES.get('accessToken')
    
    # If not in cookies, check for Authorization header manually
    if not access_token:
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            access_token = auth_header.split(' ')[1]
    
    if access_token:
        try:
            # Manually validate the token
            from rest_framework_simplejwt.tokens import UntypedToken
            from rest_framework_simplejwt.state import token_backend
            
            # Validate token
            UntypedToken(access_token)
            
            # Get user ID from token
            payload = token_backend.decode(access_token, verify=True)
            user_id = payload.get('user_id')
            
            if user_id:
                user = User.objects.get(id=user_id)
                return user, 'jwt_cookie'
                
        except (InvalidToken, TokenError, User.DoesNotExist) as e:
            logger.debug(f"JWT token validation failed: {e}")
            pass
    
    return None, None


def require_auth(redirect_url='/login/'):
    """
    Decorator that requires authentication via either Django session or JWT.
    Redirects to login page if not authenticated.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user, auth_method = get_user_from_request(request)
            
            if not user:
                return redirect(redirect_url)
            
            # Inject authenticated user into request
            request.user = user
            request.auth_method = auth_method
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class AuthMixin:
    """
    Mixin for class-based views that need authentication.
    """
    require_auth = False
    redirect_url = '/login/'
    
    def dispatch(self, request, *args, **kwargs):
        if self.require_auth:
            user, auth_method = get_user_from_request(request)
            
            if not user:
                return redirect(self.redirect_url)
            
            # Inject authenticated user into request
            request.user = user
            request.auth_method = auth_method
        
        return super().dispatch(request, *args, **kwargs)