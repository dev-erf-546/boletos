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
    
    # Admin - Panel Principal
    path('admin-panel/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin-panel/mis-ventas/', views.AdminMisVentasView.as_view(), name='admin_mis_ventas'),
    path('admin-panel/rifas/', views.AdminRifasListView.as_view(), name='admin_rifas_list'),
    path('admin-panel/rifas/nueva/', views.AdminRifaCreateView.as_view(), name='admin_rifa_create'),
    path('admin-panel/rifas/<int:pk>/', views.AdminRifaDetailView.as_view(), name='admin_rifa_detail'),
    path('admin-panel/rifas/<int:pk>/editar/', views.AdminRifaUpdateView.as_view(), name='admin_rifa_edit'),
    
    # Admin - Gestión de Usuarios
    path('admin-panel/usuarios/', views.AdminUsuariosListView.as_view(), name='admin_usuarios_list'),
    path('admin-panel/usuarios/nuevo/', views.AdminUsuarioCreateView.as_view(), name='admin_usuario_create'),
    path('admin-panel/usuarios/<int:pk>/editar/', views.AdminUsuarioUpdateView.as_view(), name='admin_usuario_edit'),
    path('admin-panel/usuarios/<int:pk>/password/', views.AdminUsuarioPasswordView.as_view(), name='admin_usuario_password'),
    path('admin-panel/usuarios/<int:pk>/toggle-activo/', views.toggle_usuario_activo, name='toggle_usuario_activo'),
    path('admin-panel/usuarios/<int:pk>/toggle-staff/', views.toggle_usuario_staff, name='toggle_usuario_staff'),
    
    # Admin - Gestión de Boletos y Comprobantes
    path('admin-panel/boletos/', views.ComprobantesPendientesView.as_view(), name='comprobantes_pendientes'),
    path('admin-panel/comprobantes/<int:pk>/validar/', views.ValidarComprobanteView.as_view(), name='validar_comprobante'),
    path('admin-panel/descargar-qrs/', views.descargar_qrs_aprobados, name='descargar_qrs'),
    path('admin-panel/rifas/<int:rifa_id>/boletos/', views.AdminGestionBoletosView.as_view(), name='admin_gestion_boletos'),
    path('admin-panel/asignar-boleto/', views.AdminAsignarBoletoView.as_view(), name='admin_asignar_boleto'),
    path(
        'admin-panel/asignar-boletos-masivo/',
        views.AdminAsignarBoletosMasivoView.as_view(),
        name='admin_asignar_boletos_masivo',
    ),
    path('admin-panel/boletos/<int:boleto_id>/reservar/', views.reservar_boleto, name='reservar_boleto'),
    path('admin-panel/reservar-boletos-masivo/', views.reservar_boletos_masivo, name='reservar_boletos_masivo'),
    path('admin-panel/generar-qr-masivo/', views.generar_qr_boletos_masivo, name='generar_qr_boletos_masivo'),
    path('admin-panel/boletos/<int:boleto_id>/editar-vendido/', views.editar_boleto_vendido, name='editar_boleto_vendido'),
    path('admin-panel/boletos/<int:boleto_id>/generar-qr/', views.generar_qr_boleto_vendido, name='generar_qr_boleto_vendido'),
    path('admin-panel/boletos/<int:boleto_id>/liberar/', views.liberar_boleto, name='liberar_boleto'),
    path(
        'admin-panel/boletos/<int:boleto_id>/liberar-vendido/',
        views.liberar_boleto_vendido,
        name='liberar_boleto_vendido',
    ),
    
    # API
    path('api/verificar-qr/<uuid:codigo_qr>/', views.verificar_qr, name='verificar_qr'),

    # Verificación pública de boleto (enlace del QR)
    path('boleto/<uuid:codigo_qr>/', views.verificar_boleto_publico, name='verificar_boleto_publico'),
    path('boletos/descarga/<uuid:token>/', views.boletos_descarga_publica, name='boletos_descarga_publica'),
    path('boletos/descarga/<uuid:token>/pdf/', views.boletos_descarga_pdf, name='boletos_descarga_pdf'),
]