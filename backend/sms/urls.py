"""API URL Configuration for SMS Portal
All endpoints return JSON responses.
Frontend HTML views are in sms_portal/frontend_urls.py
"""

from django.urls import path
from .myviews.send_sms_api import (send_sms_api, get_send_page_stats, refresh_sms_status)
from .myviews.contacts_api import get_contacts
from .myviews.groups_api import (
    get_groups,
    create_group,
    get_group_contacts,
    add_contacts_to_group,
    import_contacts_excel,
    delete_contact_from_group,
    delete_group,
)
from .myviews.Campaign_api import (get_campaigns, create_campaign)
from .myviews.Reports_api import (reports_dashboard, reports_generate)
from .myviews.templates_api import (get_templates)
from .myviews.user_management_api import (create_user_view, delete_user_view)
from .myviews.Settings_api import (
    get_settings,
    update_general_settings,
    update_sms_settings,
    test_sms_settings,
)
#from .views import (
    # SMS API
    #send_sms_api,
    #refresh_sms_status,
    #get_send_page_stats,
    
    

    # Contacts API
    #get_contacts,
    
    # Groups API
    #get_groups,
    #create_group,
    #get_group_contacts,
    #add_contacts_to_group,
    #import_contacts_excel,
    #delete_contact_from_group,
    
    # Templates API
    #get_templates,
    
    # Campaigns API
    #get_campaigns,
    #create_campaign,
    
    # Reports API
    #reports_dashboard,
    #reports_generate,
    
    # User Management API
    # create_user_view,
    #delete_user_view,
    
    # Settings API
    #get_settings,
    #update_general_settings,
    #update_sms_settings,
    #test_sms_settings,
#)

urlpatterns = [
    # SMS Sending API
    path("sms/send/", send_sms_api, name="api_send_sms_message"),
    path("messageStatus/<int:message_id>/", refresh_sms_status, name="api_refresh_sms_status"),
    path("send/stats/", get_send_page_stats, name="api_send_page_stats"),
    
    # Contacts Management API
    path("contacts/", get_contacts, name="api_contacts"),
    path("contacts/<int:contact_id>/delete/", delete_contact_from_group, name="api_delete_contact"),
    
    # Groups Management API
    path("groups/", get_groups, name="api_groups"),
    path("groups/create/", create_group, name="api_create_group"),
    path("groups/<int:group_id>/", delete_group, name="api_delete_group"),
    path("groups/<int:group_id>/contacts/", get_group_contacts, name="api_group_contacts"),
    path("groups/<int:group_id>/contacts/add/", add_contacts_to_group, name="api_add_contacts"),
    path("groups/<int:group_id>/contacts/import/", import_contacts_excel, name="api_import_contacts_excel"),
    
    # Templates API
    path("templates/", get_templates, name="api_templates"),
    
    # Campaigns API
    path("campaigns/", get_campaigns, name="api_get_campaigns"),
    path("campaigns/new/", create_campaign, name="api_create_campaign"),
    
    # Reports API
    path("reports/dashboard/", reports_dashboard, name="api_reports_dashboard"),
    path("reports/generate/", reports_generate, name="api_reports_generate"),
    
    # User Management API
    path("users/create/", create_user_view, name="api_create_user"),
    path("users/delete/", delete_user_view, name="api_delete_user"),
    
    # Settings API
    path("settings/", get_settings, name="api_get_settings"),
    path("settings/general/", update_general_settings, name="api_update_general_settings"),
    path("settings/sms/", update_sms_settings, name="api_update_sms_settings"),
    path("settings/sms/test/", test_sms_settings, name="api_test_sms_settings"),
]
