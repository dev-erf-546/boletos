from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import PermissionDenied

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """
        Redirige siempre al panel admin después del login.
        Solo administradores pueden iniciar sesión.
        """
        # Redirigir siempre al panel admin
        if hasattr(request, 'user') and request.user.is_authenticated:
            return reverse('rifas:admin_dashboard')
        
        # Si por alguna razón no está autenticado, redirigir al listado
        return reverse('rifas:listado_rifas')
    
    def is_open_for_signup(self, request):
        """
        Deshabilita el registro público. Solo administradores pueden crear cuentas.
        """
        return False
    
    def login(self, request, user):
        """
        Verificar que solo staff pueda iniciar sesión antes de hacer login.
        """
        if not user.is_staff:
            messages.error(request, "Solo los administradores pueden iniciar sesión.")
            raise PermissionDenied("Solo los administradores pueden iniciar sesión.")
        return super().login(request, user)
