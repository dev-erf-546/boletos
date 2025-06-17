import uuid
import hmac
from django.utils import timezone
from hashlib import sha256
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.conf import settings
from django.urls import reverse

#from utils import generar_qr_imagen

class Rifa(models.Model):
    nombre = models.CharField(max_length=100)
    fecha_sorteo = models.DateTimeField()
    premio_principal = models.TextField()
    descripcion = models.TextField()
    imagen = models.ImageField(upload_to='rifas/', null=True, blank=True)
    precio_boleto = models.DecimalField(max_digits=10, decimal_places=2)
    boletos_total = models.PositiveIntegerField()
    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return self.nombre
    
    def get_absolute_url(self):
        return reverse('detalle_rifa', args=[str(self.id)])
    
    @property
    def boletos_disponibles(self):
        return self.boletos.filter(estado='D').count()
    
    @property
    def boletos_vendidos(self):
        return self.boletos_total - self.boletos_disponibles

class Boleto(models.Model):
    ESTADO_CHOICES = (
        ('D', 'Disponible'),
        ('R', 'Reservado'),
        ('V', 'Vendido'),
        ('E', 'En validación'),
    )
    
    rifa = models.ForeignKey(Rifa, on_delete=models.CASCADE, related_name='boletos')
    numero = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99999)]
    )
    estado = models.CharField(max_length=1, choices=ESTADO_CHOICES, default='D')
    fecha_reserva = models.DateTimeField(null=True, blank=True)
    fecha_venta = models.DateTimeField(null=True, blank=True)
    participante = models.ForeignKey('Participante', on_delete=models.SET_NULL, null=True, blank=True, related_name='boletos')
    
    class Meta:
        unique_together = ('rifa', 'numero')
        ordering = ['numero']
    
    def __str__(self):
        return f"{self.rifa} - {self.numero}"
    
    def reservar(self, participante):
        self.estado = 'R'
        self.participante = participante
        self.fecha_reserva = timezone.now()
        self.save()
    
    def liberar(self):
        self.estado = 'D'
        self.participante = None
        self.fecha_reserva = None
        self.save()
    
    @property
    def comprobante_exists(self):
        return hasattr(self, 'comprobante')
    

class Participante(models.Model):
    METODO_CONTACTO = (
        ('WS', 'WhatsApp'),
        ('LL', 'Llamada'),
        ('FB', 'Facebook'),
        ('EM', 'Email'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    nombre_completo = models.CharField(max_length=150)
    direccion = models.CharField(max_length=200, null=True, blank=True)
    telefono = models.CharField(max_length=20)
    email = models.EmailField(null=True, blank=True)
    metodo_contacto = models.CharField(max_length=2, choices=METODO_CONTACTO, default='WS')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    reputacion = models.IntegerField(default=100)  # 0-100 escala de confiabilidad
    
    def __str__(self):
        return self.nombre_completo
    
    def puede_comprar(self):
        return self.reputacion > 30

class ComprobantePago(models.Model):
    ESTADO_CHOICES = (
        ('P', 'Pendiente'),
        ('A', 'Aprobado'),
        ('R', 'Rechazado'),
    )
    
    boleto = models.OneToOneField(Boleto, on_delete=models.CASCADE, related_name='comprobante')
    imagen = models.ImageField(
        upload_to='comprobantes/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'pdf'])]
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=1, choices=ESTADO_CHOICES, default='P')
    motivo_rechazo = models.TextField(blank=True)
    revisado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-fecha_subida']
    
    def __str__(self):
        return f"Comprobante {self.boleto} - {self.get_estado_display()}"

class QRBoleto(models.Model):
    boleto = models.OneToOneField(Boleto, on_delete=models.CASCADE, related_name='qr')
    codigo = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    imagen_qr = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    
    def __str__(self):
        return f"QR {self.boleto}"
    
    def firmar(self):
        message = f"{self.boleto.id}{self.codigo}{self.fecha_generacion.timestamp()}"
        return hmac.new(
            settings.SECRET_KEY.encode(),
            message.encode(),
            sha256
        ).hexdigest()
    
    @classmethod
    def verificar_firma(cls, codigo_qr, firma):
        try:
            qr = cls.objects.get(codigo=codigo_qr)
            return hmac.compare_digest(qr.firmar(), firma)
        except cls.DoesNotExist:
            return False

class Vendedor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telefono = models.CharField(max_length=20)
    zona = models.CharField(max_length=100)
    comision = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)  # 10% por defecto
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.zona})"

class Notificacion(models.Model):
    TIPO_CHOICES = (
        ('AP', 'Aprobación'),
        ('RE', 'Rechazo'),
        ('RE', 'Recordatorio'),
        ('SO', 'Sorteo'),
    )
    
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES)
    mensaje = models.TextField()
    fecha_envio = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    boleto = models.ForeignKey(Boleto, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-fecha_envio']
    
    def __str__(self):
        return f"Notificación {self.get_tipo_display()} para {self.participante}"
