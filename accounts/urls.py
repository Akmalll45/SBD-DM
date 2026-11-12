from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.account_dashboard, name='dashboard'),
    path('profil/', views.profile_edit, name='profile'),
    path('password/', views.AccountPasswordChangeView.as_view(), name='password'),
    path('pesanan/', views.order_list, name='orders'),
    path('pesanan/<int:order_id>/', views.order_detail, name='order_detail'),
    path('pesanan/<int:order_id>/batalkan/', views.cancel_order, name='cancel_order'),
]
