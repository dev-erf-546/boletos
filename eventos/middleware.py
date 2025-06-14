from django.core.cache import cache
from django.http import HttpResponseForbidden

class LimiteReservasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if request.path.startswith('/reservar/'):
            ip = request.META.get('REMOTE_ADDR')
            user_id = request.user.id if request.user.is_authenticated else None
            key = f"reservas_{user_id or ip}"
            
            max_reservas = 10 if user_id else 5
            count = cache.get(key, 0)
            
            if count >= max_reservas:
                return HttpResponseForbidden("Has alcanzado el límite de reservas permitidas.")
            
            cache.set(key, count + 1, 3600)  # Expira en 1 hora
        
        return self.get_response(request)