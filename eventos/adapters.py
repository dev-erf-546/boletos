from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """
        Redirige a los usuarios según su tipo después del login
        """
        if request.user.is_staff:
            return reverse('rifas:admin_dashboard')
        return reverse('rifas:listado_rifas')
