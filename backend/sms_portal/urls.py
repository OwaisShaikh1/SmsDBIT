# sms_portal/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

def home_redirect(request):
    """Redirect root to dashboard or login."""
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    return redirect('/login/')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Root redirect
    path('', home_redirect, name='home'),

    # Frontend HTML routes
    path('', include('sms_portal.frontend_urls')),

    # API routes
    path('api/', include('sms.urls')),

    path("contacts/", login_required(lambda request: render(request, "contacts.html"))),
]

# Optional custom 404
handler404 = 'sms_portal.frontend_views.custom_404_view'
