from django.urls import path
from . import views, auth_views

urlpatterns = [
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/login/demo/', auth_views.demo_login, name='demo_login'),
    path('accounts/logout/', auth_views.logout_view, name='logout'),
    path('homes/<int:pk>/contact/', auth_views.contact, name='contact'),
    path('browse/', views.browse, name='browse'),
    path('new-search/', views.new_search, name='new_search'),
    path('', views.home, name='home'),
    path('intent/', views.intent_review, name='intent'),
    path('results/', views.results, name='results'),
    path('compare/', views.compare, name='compare'),
    path('compare/toggle/', views.compare_toggle, name='compare_toggle'),
    path('homes/<int:pk>/', views.detail, name='detail'),
    path('about/', views.about, name='about'),
    path('saved/', views.saved, name='saved'),
    path('saved/toggle/', views.save_toggle, name='save_toggle'),
]
