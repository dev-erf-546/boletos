# Modificado: 2026-03-17 22:10:50 - Configuración de redirect al admin-panel después del login
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
        # Siempre redirigir al panel admin después del login exitoso
        # El usuario ya está autenticado cuando se llama este método
        return reverse('rifas:admin_dashboard')
    
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
