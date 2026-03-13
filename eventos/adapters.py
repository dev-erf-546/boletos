from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """
        Redirige a los usuarios según su tipo después del login
        """
        # Verificar que el usuario esté autenticado y tenga el atributo is_staff
        if request.user.is_authenticated and hasattr(request.user, 'is_staff') and request.user.is_staff:
            return reverse('rifas:admin_dashboard')
        return reverse('rifas:listado_rifas')
    
    def is_open_for_signup(self, request):
        """
        Permite el registro de nuevos usuarios
        """
        return True
