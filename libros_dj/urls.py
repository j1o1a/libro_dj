from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', auth_views.LoginView.as_view(
        template_name='core/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('ordinarios/', include('ordinarios.urls')),
    path('memorandos/', include('memorandos.urls')),
    path('ajustes/', include('ajustes.urls')),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('__debug__/', include('debug_toolbar.urls')),
]