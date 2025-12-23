# myapp08/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('events/', views.event_list, name='event_list'),
    path('event/<int:pk>/', views.event_detail, name='event_detail'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('confirmation/', views.confirmation_page, name='confirmation_page'),

   
    path('event/create/', views.event_create, name='event_create'),
    path('event/<int:pk>/book/', views.book_event, name='book_event'),
    path('event/<int:pk>/pay/', views.pay_event, name='pay_event'),
    path('event/<int:pk>/rsvp/', views.rsvp_event, name='rsvp_event'),
    path('event/<int:pk>/pay/', views.pay_event, name='pay_event'),

  
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/organizer/', views.organizer_dashboard, name='organizer_dashboard'),
    path('dashboard/attendee/', views.attendee_dashboard, name='attendee_dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),

    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup_view, name="signup"),

    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/admin/analytics/', views.admin_analytics, name='admin_analytics'),
    path('dashboard/admin/analytics/data/', views.analytics_json, name='analytics_json'),

    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),  


    path('certificate/download/<int:ticket_id>/', views.download_certificate, name='download_certificate'),

]







   

   