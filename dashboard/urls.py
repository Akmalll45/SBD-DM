from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # 1. Overview
    path('', views.admin_dashboard, name='dashboard'),

    # 2. Site & Brand Settings
    path('settings/', views.site_settings, name='site_settings'),

    # 3. Orders & Sablon
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),

    # 4. Products & Inventory
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:product_id>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:product_id>/delete/', views.product_delete, name='product_delete'),

    # 5. Customers
    path('customers/', views.customer_list, name='customer_list'),

    # 6. Articles / CMS
    path('articles/', views.article_list, name='article_list'),
    path('articles/create/', views.article_create, name='article_create'),
    path('articles/<int:article_id>/edit/', views.article_edit, name='article_edit'),
    path('articles/<int:article_id>/delete/', views.article_delete, name='article_delete'),
]

