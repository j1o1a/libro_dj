from django.urls import path
from .views import OrdinarioListView, OrdinarioCreateView

app_name = 'ordinarios'
urlpatterns = [
    path('', OrdinarioListView.as_view(), name='lista'),
    path('crear/', OrdinarioCreateView.as_view(), name='crear'),
]