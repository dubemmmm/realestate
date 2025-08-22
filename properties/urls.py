from django.urls import path
from . import views

urlpatterns = [
    path("", views.landing_view, name='landing'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/properties/', views.properties_api, name='properties_api'),
    path('api/properties/<int:property_id>/', views.property_detail_api, name='property_detail_api'),
    # path('login', views.login, name='login'),
    path('api/create-shared-list/', views.create_shared_list, name='create_shared_list'),
    path('shared/<str:token>/', views.shared_properties_view, name='shared_properties'),
    path('manage-shares/', views.manage_shared_lists, name='manage_shared_lists'),
    path('register/', views.register_view, name='register'),
    path('manage-shares/delete/<int:list_id>/', views.delete_shared_list, name='delete_shared_list'),
    path('manage-shares/toggle/<int:list_id>/', views.toggle_shared_link, name='toggle_shared_list'),
    path('admins/create-employee/', views.create_employee_view, name='create_employee'),
    path('api/sync-airtable/', views.sync_airtable, name='sync_airtable'),
    path('property/<int:property_id>/pdf/', views.download_property_pdf, name='property_pdf'),
    
    # Property Comparison URLs
    path('api/compare-properties/', views.compare_properties, name='compare_properties'),
    path('comparison/<str:property_ids>/pdf/', views.download_comparison_pdf, name='comparison_pdf'),
    # path('api/airtable/property/<str:property_id>/', views.airtable_property_detail_api, name='airtable_property_detail_api'),
    # path('api/airtable/properties/', views.airtable_all_properties_api, name='airtable_all_properties_api'),
    
    
]