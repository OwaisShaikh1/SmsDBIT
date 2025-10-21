from django.urls import path
from .views import get_contacts, sidebar_view, dashboard_page, get_groups, get_templates, send_sms

urlpatterns = [
    path("contacts/", get_contacts, name="api_contacts"),   # /api/contacts/
    path("sidebar/", sidebar_view, name="sidebar_view"),
    path("dashboard/", dashboard_page, name="dashboard_page"),
    path("groups/", get_groups, name="api_groups"),
    path("templates/", get_templates, name="api_templates"),
    path("sms/send/", send_sms, name="api_send_sms_message"),
]
