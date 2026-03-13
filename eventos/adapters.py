from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """
        Redirige a los usuarios al panel admin después del login.
        Todos los usuarios autenticados van al admin-panel.
        """
        # En este punto, el usuario ya debería estar autenticado
        # Redirigir siempre al panel admin
        if hasattr(request, 'user') and request.user.is_authenticated:
            return reverse('rifas:admin_dashboard')
        
        # Si por alguna razón no está autenticado, redirigir al listado
        return reverse('rifas:listado_rifas')
    
    def is_open_for_signup(self, request):
        """
        Permite el registro de nuevos usuarios
        """
        return True
