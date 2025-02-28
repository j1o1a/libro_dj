from django.contrib import admin
from django.urls import path, include
from core.views import CustomLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', CustomLoginView.as_view(), name='login'),
    path('ordinarios/', include('ordinarios.urls')),
    path('memorandos/', include('memorandos.urls')),
    path('ajustes/', include('ajustes.urls')), 
]