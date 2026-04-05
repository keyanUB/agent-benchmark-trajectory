from django.urls import path
from myapp import views

urlpatterns = [
    path('convert', views.convert, name='convert'),
]