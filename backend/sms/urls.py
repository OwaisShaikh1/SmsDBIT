from django.urls import path
from .views import (
    get_contacts, sidebar_view, dashboard_page, get_groups, get_templates, 
    send_sms, get_campaigns, create_campaign, create_group, reports_dashboard, 
    reports_generate, create_user_view, delete_user_view, get_settings, update_general_settings,
    update_sms_settings, test_sms_settings, get_send_page_stats
)

urlpatterns = [
    path("contacts/", get_contacts, name="api_contacts"),   # /api/contacts/
    path("sidebar/", sidebar_view, name="sidebar_view"),
    path("dashboard/", dashboard_page, name="dashboard_page"),
    path("groups/", get_groups, name="api_groups"),
    path("groups/create/", create_group, name="api_create_group"),
    path("templates/", get_templates, name="api_templates"),
    path("reports/dashboard/", reports_dashboard, name="api_reports_dashboard"),
    path("reports/generate/", reports_generate, name="api_reports_generate"),
    path("sms/send/", send_sms, name="api_send_sms_message"),
    path("campaigns/", get_campaigns, name="api_get_campaigns"),
    path("campaigns/new/", create_campaign, name="api_create_campaign"),
    path("users/create/", create_user_view, name="api_create_user"),
    path("users/delete/", delete_user_view, name="api_delete_user"),
    path("settings/", get_settings, name="api_get_settings"),
    path("settings/general/", update_general_settings, name="api_update_general_settings"),
    path("settings/sms/", update_sms_settings, name="api_update_sms_settings"),
    path("settings/sms/test/", test_sms_settings, name="api_test_sms_settings"),
    path("send/stats/", get_send_page_stats, name="api_send_page_stats"),

]
