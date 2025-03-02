from django.urls import path
from . import views

urlpatterns = [
    path('', views.memorandos_lista, name='memorandos_lista'),
    path('agregar/', views.memorandos_agregar, name='memorandos_agregar'),
    path('editar/<int:pk>/', views.memorandos_editar, name='memorandos_editar'),
    path('anular/<int:pk>/', views.memorandos_anular, name='memorandos_anular'),
    path('bloquear/', views.memorandos_bloquear, name='memorandos_bloquear'),
]