from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.account_dashboard, name='dashboard'),
    path('profil/', views.profile_edit, name='profile'),
    path('profil/email/kirim-verifikasi/', views.send_email_verification, name='send_email_verification'),
    path('profil/email/verifikasi/<str:token>/', views.verify_email, name='verify_email'),
    path('profil/telepon/kirim-kode/', views.send_phone_verification, name='send_phone_verification'),
    path('profil/telepon/verifikasi/', views.verify_phone, name='verify_phone'),
    path('alamat/tambah/', views.address_edit, name='address_add'),
    path('alamat/<int:address_id>/ubah/', views.address_edit, name='address_edit'),
    path('alamat/<int:address_id>/hapus/', views.address_delete, name='address_delete'),
    path('alamat/<int:address_id>/utama/', views.address_set_primary, name='address_set_primary'),
    path('keamanan/', views.account_security, name='security'),
    path('keamanan/totp/mulai/', views.start_totp_setup, name='totp_setup'),
    path('keamanan/totp/konfirmasi/', views.confirm_totp_setup, name='totp_confirm'),
    path('keamanan/totp/nonaktifkan/', views.disable_totp, name='totp_disable'),
    path('keamanan/keluar-perangkat-lain/', views.logout_other_devices, name='logout_other_devices'),
    path('masuk/verifikasi/', views.totp_login_page, name='totp_login'),
    path('password/', views.AccountPasswordChangeView.as_view(), name='password'),
    path('pesanan/', views.order_list, name='orders'),
    path('pesanan/<int:order_id>/', views.order_detail, name='order_detail'),
    path('pesanan/<int:order_id>/batalkan/', views.cancel_order, name='cancel_order'),
]
