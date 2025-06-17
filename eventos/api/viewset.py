from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from eventos.models import Rifa, Boleto
from .serializers import BoletoSerializer, RifaSerializer

class RifaBoletosAPIView(generics.ListAPIView):
    serializer_class = BoletoSerializer
    
    def get_queryset(self):
        rifa_id = self.kwargs['pk']
        return Boleto.objects.filter(rifa_id=rifa_id).order_by('numero')

class RifaDetailAPIView(APIView):
    def get(self, request, pk):
        rifa = Rifa.objects.get(pk=pk)
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