from django.http import Http404
from django.shortcuts import render
from django.template.exceptions import TemplateDoesNotExist
from django.utils.deprecation import MiddlewareMixin


class Custom404Middleware(MiddlewareMixin):
    """
    Middleware to catch all 404 errors and template not found errors
    and render them with our custom 404 page that includes sidebar
    """
    
    def process_exception(self, request, exception):
        # Handle TemplateDoesNotExist errors as 404s
        if isinstance(exception, TemplateDoesNotExist):
            return render(request, '404.html', status=404)
        
        # Handle Http404 errors
        if isinstance(exception, Http404):
            return render(request, '404.html', status=404)
            
        # Let other exceptions pass through
        return None


class Custom404ResponseMiddleware:
    """
    Alternative middleware to catch 404 responses and replace them
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # If it's a 404 response, replace with our custom 404 page
        if response.status_code == 404:
            return render(request, '404.html', status=404)
            
        return response