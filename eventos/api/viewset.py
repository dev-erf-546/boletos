from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from eventos.models import Rifa, Boleto
from .serializers import BoletoSerializer, RifaSerializer

MENSAJE_VENTAS_FINALIZADAS = 'Las ventas han finalizado.'


class RifaBoletosAPIView(generics.ListAPIView):
    serializer_class = BoletoSerializer
    
    def list(self, request, *args, **kwargs):
        rifa = get_object_or_404(Rifa, pk=self.kwargs['pk'])
        if not rifa.activa:
            return Response({'detail': MENSAJE_VENTAS_FINALIZADAS}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        rifa_id = self.kwargs['pk']
        return Boleto.objects.filter(rifa_id=rifa_id).order_by('numero')

class RifaDetailAPIView(APIView):
    def get(self, request, pk):
        rifa = get_object_or_404(Rifa, pk=pk)
        if not rifa.activa:
            return Response({'detail': MENSAJE_VENTAS_FINALIZADAS}, status=status.HTTP_403_FORBIDDEN)

        boletos = Boleto.objects.filter(rifa=rifa).order_by('numero')
        
        rifa_serializer = RifaSerializer(rifa)
        boletos_serializer = BoletoSerializer(boletos, many=True)
        
        return Response({
            'rifa': rifa_serializer.data,
            'boletos': boletos_serializer.data,
            'stats': {
                'total': rifa.boletos_total,
                'disponibles': rifa.boletos_disponibles,
                'vendidos': rifa.boletos_vendidos,
            }
        })