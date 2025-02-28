from django.urls import path
from . import views

urlpatterns = [
    path('', views.ordinarios_lista, name='ordinarios_lista'),
    path('agregar/', views.ordinarios_agregar, name='ordinarios_agregar'),
    path('editar/<int:pk>/', views.ordinarios_editar, name='ordinarios_editar'),
    path('anular/<int:pk>/', views.ordinarios_anular, name='ordinarios_anular'),
]