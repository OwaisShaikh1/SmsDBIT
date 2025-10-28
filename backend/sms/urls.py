from django.urls import path
from .views import get_contacts, sidebar_view, dashboard_page, get_groups, get_templates, send_sms, get_campaigns, create_campaign, create_group

urlpatterns = [
    path("contacts/", get_contacts, name="api_contacts"),   # /api/contacts/
    path("sidebar/", sidebar_view, name="sidebar_view"),
    path("dashboard/", dashboard_page, name="dashboard_page"),
    path("groups/", get_groups, name="api_groups"),
    path("groups/create/", create_group, name="api_create_group"),
    path("templates/", get_templates, name="api_templates"),
    path("sms/send/", send_sms, name="api_send_sms_message"),
    path("campaigns/", get_campaigns, name="api_get_campaigns"),
    path("campaigns/new/", create_campaign, name="api_create_campaign"),

]
