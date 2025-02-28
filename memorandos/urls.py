from django.urls import path
from .views import MemorandoListView, MemorandoCreateView

app_name = 'memorandos'
urlpatterns = [
    path('', MemorandoListView.as_view(), name='lista'),
    path('crear/', MemorandoCreateView.as_view(), name='crear'),
]