# Modificado: 2026-03-17 23:30:00 - Mixin robusto para proteger vistas admin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin robusto que requiere que el usuario esté autenticado y sea staff.
    Redirige al login si no cumple los requisitos.
    """
    login_url = '/admin/login/'
    redirect_field_name = 'next'
    
    def test_func(self):
        """Verifica que el usuario sea staff y esté activo"""
        user = self.request.user
        return user.is_authenticated and user.is_staff and user.is_active
    
    def handle_no_permission(self):
        """Redirige al login si no tiene permisos"""
        if not self.request.user.is_authenticated:
            messages.warning(self.request, 'Debes iniciar sesión para acceder a esta página.')
            return redirect(f'{self.login_url}?next={self.request.path}')
        else:
            messages.error(self.request, 'No tienes permisos para acceder a esta página.')
            return redirect('/admin/login/')
    
    def dispatch(self, request, *args, **kwargs):
        """Intercepta todas las peticiones para verificar permisos"""
        if not request.user.is_authenticated:
            return redirect(f'{self.login_url}?next={request.path}')
        
        if not request.user.is_staff:
            messages.error(request, 'Solo los administradores pueden acceder a esta sección.')
            return redirect('/admin/login/')
        
        if not request.user.is_active:
            messages.error(request, 'Tu cuenta está desactivada.')
            return redirect('/admin/login/')
        
        return super().dispatch(request, *args, **kwargs)
