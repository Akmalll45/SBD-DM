from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    # Storefront & Catalog
    path('', views.home, name='home'),
    path('tentang-kami/', views.about, name='about'),
    path('shop/', views.product_list, name='shop'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('product/<slug:slug>/rate/', views.rate_product, name='rate_product'),

    # Cart Operations
    path('cart/', views.cart_detail, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_cart_item, name='remove_cart_item'),

    # Checkout & Confirmation
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/konfirmasi/', views.checkout_confirm, name='checkout_confirm'),
    path('pesanan/<int:order_id>/bayar/', views.payment_detail, name='payment_detail'),
    path('order/<int:order_id>/success/', views.order_success, name='order_success'),
    path('pesanan/<int:order_id>/invoice.pdf', views.invoice_pdf, name='invoice_pdf'),
    path('pesanan/<int:order_id>/bukti-transfer/', views.payment_proof_file, name='payment_proof_file'),
    path('pembayaran/midtrans/notifikasi/', views.midtrans_notification, name='midtrans_notification'),

    # Auth
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.LogoutUserView.as_view(), name='logout'),
]
