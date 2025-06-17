from rest_framework import serializers
from eventos.models import Boleto, Rifa

class BoletoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    class Meta:
        model = Boleto
        fields = ['id', 'numero', 'estado', 'estado_display', 'fecha_reserva', 'fecha_venta', 'participante']
        read_only_fields = ['id', 'numero', 'rifa']

class RifaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rifa
        fields = ['id', 'nombre', 'precio_boleto']