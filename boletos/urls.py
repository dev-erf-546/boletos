from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views 

urlpatterns = [
    path('', include('eventos.urls', namespace='rifas')),
    path('admin/', admin.site.urls),

    #path('usuario/login/', auth_views.LoginView.as_view(template_name='rifas/login.html'), name='login'),
    #path('usuario/logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('usuario/', include('allauth.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
