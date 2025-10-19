from django.conf import settings

def api_settings(request):
    """
    Add API_BASE and other useful settings to template context.
    """
    return {
        'API_BASE': getattr(settings, 'API_BASE', '/api'),
        'DEBUG': settings.DEBUG,
    }