# Modificado: 2026-03-17 22:10:50 - Vista personalizada de login para admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponse

@never_cache
@csrf_protect
def custom_admin_login(request):
    """
    Vista personalizada de login que usa nuestro template personalizado.
    """
    # Si ya está autenticado y es staff, redirigir
    if request.user.is_authenticated and request.user.is_staff:
        next_url = request.GET.get('next', '/admin-panel/')
        return redirect(next_url)
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            from django.contrib.auth import login
            user = form.get_user()
            # Verificar que sea staff
            if not user.is_staff:
                form.add_error(None, 'Solo los administradores pueden acceder.')
            else:
                login(request, user)
                next_url = request.POST.get('next', '/admin-panel/')
                return redirect(next_url)
    else:
        form = AuthenticationForm(request)
    
    # Renderizar el template con RequestContext para que el CSRF token funcione
    from django.template.loader import get_template
    from django.template import RequestContext
    
    template = get_template('admin/login.html')
    context = {
        'form': form,
        'next': request.GET.get('next', '/admin-panel/'),
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
    }
    # Usar RequestContext para que el CSRF token se genere correctamente
    html = template.render(context, request)
    return HttpResponse(html)

# Configurar el AdminSite para usar nuestra vista personalizada
admin.site.login = custom_admin_login

urlpatterns = [
    path('', include('eventos.urls', namespace='rifas')),
    path('admin/', admin.site.urls),

    # URLs de allauth deshabilitadas - solo se usa el admin de Django para login
    # path('usuario/', include('allauth.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
