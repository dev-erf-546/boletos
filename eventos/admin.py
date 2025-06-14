from django.contrib import admin
from .models import Rifa, Boleto, Participante, ComprobantePago, QRBoleto, Vendedor, Notificacion

# Configuración personalizada para cada modelo
class BoletoInline(admin.TabularInline):
    model = Boleto
    extra = 0
    readonly_fields = ['estado', 'fecha_reserva', 'fecha_venta']
    fields = ['numero', 'estado', 'participante', 'fecha_reserva', 'fecha_venta']

@admin.register(Rifa)
class RifaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'fecha_sorteo', 'precio_boleto', 'boletos_total', 'boletos_vendidos', 'activa']
    list_filter = ['activa', 'fecha_sorteo']
    search_fields = ['nombre', 'descripcion']
    inlines = [BoletoInline]
    
    def boletos_vendidos(self, obj):
        return obj.boletos.filter(estado='V').count()
    boletos_vendidos.short_description = 'Boletos Vendidos'

@admin.register(Boleto)
class BoletoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'rifa', 'estado', 'participante', 'fecha_venta']
    list_filter = ['estado', 'rifa']
    search_fields = ['numero', 'participante__nombre_completo']
    raw_id_fields = ['participante']

@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'telefono', 'email', 'metodo_contacto', 'reputacion']
    search_fields = ['nombre_completo', 'telefono', 'email']
    list_filter = ['metodo_contacto']

@admin.register(ComprobantePago)
class ComprobantePagoAdmin(admin.ModelAdmin):
    list_display = ['boleto', 'estado', 'fecha_subida', 'revisado_por']
    list_filter = ['estado', 'fecha_subida']
    readonly_fields = ['imagen_preview']
    
    def imagen_preview(self, obj):
        from django.utils.html import format_html
        return format_html('<img src="{}" style="max-height: 200px;"/>', obj.imagen.url)
    imagen_preview.short_description = "Vista previa"

@admin.register(QRBoleto)
class QRBoletoAdmin(admin.ModelAdmin):
    list_display = ['boleto', 'codigo', 'fecha_generacion', 'activo']
    readonly_fields = ['codigo', 'fecha_generacion']

@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ['user', 'zona', 'comision', 'activo']
    list_filter = ['zona', 'activo']

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['participante', 'tipo', 'fecha_envio', 'leida']
    list_filter = ['tipo', 'leida']
    search_fields = ['participante__nombre_completo']
