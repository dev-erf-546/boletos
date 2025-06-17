from django.urls import path
from . import views
from eventos.api.viewset import RifaBoletosAPIView, RifaDetailAPIView

app_name = 'eventos'

urlpatterns = [
    # Públicas
    path('', views.RifaListView.as_view(), name='listado_rifas'),
    path('<int:pk>/', views.RifaDetailView.as_view(), name='detalle_rifa'),
    path('api/rifas/<int:pk>/boletos/', RifaBoletosAPIView.as_view(), name='rifa-boletos-api'),
    path('api/rifas/<int:pk>/', RifaDetailAPIView.as_view(), name='rifa-detail-api'),
    
    # Autenticadas
    path('<int:rifa_id>/seleccionar/', views.SeleccionNumeroView.as_view(), name='seleccion_numero'),
    path('registro/', views.RegistroParticipanteView.as_view(), name='registro_participante'),
    path('mis-boletos/', views.MisBoletosView.as_view(), name='mis_boletos'),
    path('subir-comprobante/<int:boleto_id>/', views.SubirComprobanteView.as_view(), name='subir_comprobante'),
    path('boleto/<int:boleto_id>/qr/', views.MostrarQRView.as_view(), name='mostrar_qr'),
    
    # Admin
    path('admin/boletos/', views.ComprobantesPendientesView.as_view(), name='comprobantes_pendientes'),
    path('admin/comprobantes/<int:pk>/validar/', views.ValidarComprobanteView.as_view(), name='validar_comprobante'),
    path('admin/descargar-qrs/', views.descargar_qrs_aprobados, name='descargar_qrs'),
    path('admin/rifas/<int:rifa_id>/boletos/', views.AdminGestionBoletosView.as_view(), name='admin_gestion_boletos'),
    path('admin/asignar-boleto/', views.AdminAsignarBoletoView.as_view(), name='admin_asignar_boleto'),
    path('admin/boletos/<int:boleto_id>/reservar/', views.reservar_boleto, name='reservar_boleto'),
    path('admin/boletos/<int:boleto_id>/liberar/', views.liberar_boleto, name='liberar_boleto'),
    
    # API
    path('api/verificar-qr/<uuid:codigo_qr>/', views.verificar_qr, name='verificar_qr'),
]