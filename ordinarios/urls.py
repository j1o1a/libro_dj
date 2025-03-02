from django.urls import path
from . import views

urlpatterns = [
    path('', views.ordinarios_lista, name='ordinarios_lista'),
    path('agregar/', views.ordinarios_agregar, name='ordinarios_agregar'),
    path('<int:pk>/editar/', views.ordinarios_editar, name='ordinarios_editar'),
    path('<int:pk>/anular/', views.ordinarios_anular, name='ordinarios_anular'),
    path('<int:pk>/eliminar/', views.ordinarios_eliminar, name='ordinarios_eliminar'),
    path('bloquear/', views.ordinarios_bloquear, name='ordinarios_bloquear'),
]