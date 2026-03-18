# Modificado: 2026-03-17 22:10:50 - Eliminada URL /usuario/login/ de allauth, solo se usa /admin/login/
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

# Configurar el template personalizado para el login del admin
admin.site.login_template = 'admin/login.html'

urlpatterns = [
    path('', include('eventos.urls', namespace='rifas')),
    path('admin/', admin.site.urls),

    # URLs de allauth deshabilitadas - solo se usa el admin de Django para login
    # path('usuario/', include('allauth.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
