from django.urls import path

from . import views

urlpatterns = [
    path(
        'mpesa/callback/',
        views.mpesa_callback,
        name='mpesa_callback',
    ),
    path(
        'status/<str:token>/',
        views.payment_status,
        name='payment_status',
    ),
]
