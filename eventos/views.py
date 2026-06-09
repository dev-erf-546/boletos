import uuid
import json
from django.db.models import Q, Count
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, Http404, FileResponse, HttpResponse
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST
from django.conf import settings
import os
import textwrap
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, user_passes_test

from .mixins import StaffRequiredMixin

from .models import (
    Rifa,
    Boleto,
    Participante,
    ComprobantePago,
    QRBoleto,
    Notificacion,
    LoteBoletosMasivo,
)
from .forms import (
    RegistroParticipanteForm, 
    SubirComprobanteForm, 
    ValidarComprobanteForm,
    RifasCaptchaForm,
    RifaForm,
    UsuarioCreateForm,
    UsuarioEditForm,
    UsuarioPasswordForm
)
from django.contrib.auth.models import User

from .utils import generar_qr_boleto

logger = logging.getLogger(__name__)

MENSAJE_BOLETOS_DIGITALES_PENDIENTES = (
    'No hay boletos generados aun, pide a tu administrador de ventas genere tus boletos digitales.'
)


def _pdf_truncar(texto, max_len=42):
    if not texto:
        return 'N/A'
    s = str(texto)
    return s if len(s) <= max_len else s[: max_len - 1] + '…'


def _pdf_dibujar_boleto_en_celda(pdf, boleto, x0, y_top, cell_w, cell_h):
    """
    Dibuja solo la imagen del boleto/QR dentro de una celda.
    y_top = borde superior de la celda (coord. ReportLab).
    """
    pad = 2 * mm

    qr = getattr(boleto, 'qr', None)
    if qr and qr.imagen_qr:
        try:
            img_w = max(1, cell_w - (2 * pad))
            img_h = max(1, cell_h - (2 * pad))
            img_x = x0 + pad
            img_y = y_top - cell_h + pad
            pdf.drawImage(
                qr.imagen_qr.path,
                img_x,
                img_y,
                width=img_w,
                height=img_h,
                preserveAspectRatio=True,
                mask='auto',
            )
        except Exception as exc:
            logger.warning('No se pudo incrustar QR en PDF para boleto %s: %s', boleto.numero, exc)


class RifaListView(ListView):
    model = Rifa
    template_name = 'rifas/listado.html'
    context_object_name = 'rifas'
    
    def get_queryset(self):
        return Rifa.objects.filter(activa=True).order_by('fecha_sorteo')

class RifaDetailView(DetailView):
    model = Rifa
    template_name = 'rifas/detalle.html'
    context_object_name = 'rifa'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rifa = self.object
        
        # Estadísticas detalladas
        boletos_vendidos = rifa.boletos.filter(estado='V').count()
        boletos_reservados = rifa.boletos.filter(estado='R').count()
        boletos_disponibles = rifa.boletos.filter(estado='D').count()
        boletos_validacion = rifa.boletos.filter(estado='E').count()
        
        # Porcentajes para visualización
        total = rifa.boletos_total
        porcentaje_vendidos = (boletos_vendidos / total * 100) if total > 0 else 0
        porcentaje_reservados = (boletos_reservados / total * 100) if total > 0 else 0
        porcentaje_disponibles = (boletos_disponibles / total * 100) if total > 0 else 0
        
        # Ingresos estimados
        ingresos_totales = boletos_vendidos * rifa.precio_boleto
        
        context.update({
            'boletos_disponibles': boletos_disponibles,
            'boletos_vendidos': boletos_vendidos,
            'boletos_reservados': boletos_reservados,
            'boletos_validacion': boletos_validacion,
            'porcentaje_vendidos': round(porcentaje_vendidos, 1),
            'porcentaje_reservados': round(porcentaje_reservados, 1),
            'porcentaje_disponibles': round(porcentaje_disponibles, 1),
            'ingresos_totales': ingresos_totales,
            'api_url': reverse('rifas:rifa-detail-api', args=[str(rifa.id)]),
        })
        return context

class SeleccionNumeroView(View):
    def get(self, request, rifa_id):
        rifa = get_object_or_404(Rifa, id=rifa_id, activa=True)
        return render(request, 'rifas/seleccion_numero.html', {
            'rifa': rifa,
            'captcha_form': RifasCaptchaForm()
        })
    
    def post(self, request, rifa_id):
        rifa = get_object_or_404(Rifa, id=rifa_id, activa=True)
        form = RifasCaptchaForm(request.POST)
        
        if not form.is_valid():
            return render(request, 'rifas/seleccion_numero.html', {
                'rifa': rifa,
                'captcha_form': form,
                'error': 'Verificación incorrecta'
            })
        
        numeros_seleccionados = request.POST.getlist('numeros')
        
        if not numeros_seleccionados:
            return render(request, 'rifas/seleccion_numero.html', {
                'rifa': rifa,
                'captcha_form': RifasCaptchaForm(),
                'error': 'Debes seleccionar al menos un número'
            })
        
        # Verificar disponibilidad
        boletos = []
        with transaction.atomic():
            for num in numeros_seleccionados:
                boleto = Boleto.objects.select_for_update().filter(
                    rifa=rifa,
                    numero=num,
                    estado='D'
                ).first()
                
                if not boleto:
                    return render(request, 'rifas/seleccion_numero.html', {
                        'rifa': rifa,
                        'captcha_form': RifasCaptchaForm(),
                        'error': f'El número {num} ya no está disponible'
                    })
                
                boletos.append(boleto)
            
            # Todos disponibles, proceder con reserva
            # Guardar los números seleccionados en sesión para el registro
            for boleto in boletos:
                boleto.estado = 'R'  # Reservar temporalmente
                boleto.save()
        
        request.session['boletos_reservados'] = [b.id for b in boletos]
        return redirect('rifas:registro_participante')

class RegistroParticipanteView(View):
    def get(self, request):
        boletos_ids = request.session.get('boletos_reservados', [])
        if not boletos_ids:
            return redirect('rifas:listado_rifas')
        
        boletos = Boleto.objects.filter(id__in=boletos_ids, estado='R')
        form = RegistroParticipanteForm()
        
        return render(request, 'rifas/registro_participante.html', {
            'form': form,
            'boletos': boletos
        })
    
    def post(self, request):
        boletos_ids = request.session.get('boletos_reservados', [])
        if not boletos_ids:
            return redirect('rifas:listado_rifas')
        
        boletos = Boleto.objects.filter(id__in=boletos_ids, estado='R')
        form = RegistroParticipanteForm(request.POST)
        
        if form.is_valid():
            # Crear participante sin usuario
            participante = form.save(commit=False)
            participante.save()
            
            # Asignar participante a los boletos y cambiar estado
            for boleto in boletos:
                boleto.participante = participante
                boleto.estado = 'E'  # En validación
                boleto.fecha_venta = timezone.now()
                boleto.save()
            
            del request.session['boletos_reservados']
            messages.success(request, "¡Boletos reservados! Ahora sube tu comprobante de pago.")
            return redirect('rifas:subir_comprobante', boleto_id=boletos.first().id)
        
        return render(request, 'rifas/registro_participante.html', {
            'form': form,
            'boletos': boletos
        })

class SubirComprobanteView(View):
    def get(self, request, boleto_id):
        boleto = get_object_or_404(Boleto, id=boleto_id, estado='E')
        form = SubirComprobanteForm()
        
        return render(request, 'rifas/subir_comprobante.html', {
            'form': form,
            'boleto': boleto
        })
    
    def post(self, request, boleto_id):
        boleto = get_object_or_404(Boleto, id=boleto_id, estado='E')
        form = SubirComprobanteForm(request.POST, request.FILES)
        
        if form.is_valid():
            comprobante = form.save(commit=False)
            comprobante.boleto = boleto
            comprobante.save()
            
            messages.success(request, "Comprobante subido correctamente. En revisión.")
            return redirect('rifas:mis_boletos')
        
        return render(request, 'rifas/subir_comprobante.html', {
            'form': form,
            'boleto': boleto
        })

class MisBoletosView(LoginRequiredMixin, ListView):
    template_name = 'rifas/mis_boletos.html'
    context_object_name = 'boletos'
    
    def get_queryset(self):
        return Boleto.objects.filter(
            participante__user=self.request.user
        ).order_by('-fecha_venta', 'rifa__fecha_sorteo')

class MostrarQRView(View):
    def get(self, request, boleto_id):
        boleto = get_object_or_404(Boleto, id=boleto_id, estado='V')
        
        # Crear o regenerar QR si no existe o si la imagen no está generada
        if not hasattr(boleto, 'qr'):
            qr = QRBoleto.objects.create(boleto=boleto)
            generar_qr_boleto(qr)  # La función guarda la imagen internamente
        elif not boleto.qr.imagen_qr:
            # Si existe el QR pero no tiene imagen, generarla
            generar_qr_boleto(boleto.qr)
        # Si se solicita regenerar (parámetro ?regenerar=1)
        elif request.GET.get('regenerar') == '1':
            generar_qr_boleto(boleto.qr)
            messages.success(request, "Boleto regenerado con el nuevo diseño")
        
        return render(request, 'rifas/mostrar_qr.html', {
            'boleto': boleto
        })

# Vistas de Administración

class ComprobantesPendientesView(StaffRequiredMixin, ListView):
    model = Boleto
    template_name = 'rifas/admin/comprobantes_pendientes.html'
    context_object_name = 'boletos'

    def get_queryset(self):
        boletos = Boleto.objects.filter(
            estado__in=['V', 'R']
        ).select_related(
            'vendido_por',
            'rifa',
        ).order_by('rifa_id', 'numero')

        rifa_id = self.request.GET.get('rifa')
        if rifa_id:
            boletos = boletos.filter(rifa_id=rifa_id)

        inicio = self.request.GET.get('inicio')
        fin = self.request.GET.get('fin')
        if inicio:
            boletos = boletos.filter(numero__gte=inicio)
        if fin:
            boletos = boletos.filter(numero__lte=fin)

        return boletos

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'current_rifa': self.request.GET.get('rifa', ''),
            'current_inicio': self.request.GET.get('inicio', ''),
            'current_fin': self.request.GET.get('fin', ''),
            'rifas': Rifa.objects.order_by('-fecha_creacion'),
        })
        return context


class ValidarComprobanteView(StaffRequiredMixin, UpdateView):
    model = ComprobantePago
    form_class = ValidarComprobanteForm
    template_name = 'rifas/admin/validar_comprobante.html'
    success_url = reverse_lazy('rifas:comprobantes_pendientes')
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_object(self, queryset=None):
        object_id = self.kwargs.get('object_id') or self.kwargs.get('pk')
        return get_object_or_404(ComprobantePago, pk=object_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comprobante'] = self.object
        context['qr_existe'] = hasattr(self.object.boleto, 'qr')
        return context
    
    def form_valid(self, form):
        form.instance.revisado_por = self.request.user
        form.instance.fecha_revision = timezone.now()
        
        response = super().form_valid(form)
        boleto = form.instance.boleto
        
        if form.instance.estado == 'A':
            boleto.estado = 'V'
            boleto.vendido_por = self.request.user

            if not boleto.participante:
                boleto.participante = form.instance.participante

            boleto.save()
            
            # Generar o actualizar QR - SOLO AQUÍ SE CREA LA INSTANCIA
            qr_instance, created = QRBoleto.objects.get_or_create(
                boleto=boleto,
                defaults={'codigo': str(uuid.uuid4())}
            )
            
            # Generar el QR - PASAMOS LA INSTANCIA DIRECTAMENTE
            try:
                if not generar_qr_boleto(qr_instance):  # Cambio clave aquí
                    messages.error(self.request, "Error generando el boleto con QR")
                else:
                    messages.success(self.request, "Boleto aprobado y QR generado correctamente")
            
            except Exception as e:
                logger.error(f"Error generando QR para boleto {boleto.id}: {str(e)}")
                messages.error(self.request, "Error técnico al generar el QR")
            
            # Notificar al usuario
            Notificacion.objects.create(
                participante=boleto.participante,
                tipo='AP',
                mensaje=f"Tu comprobante para el boleto {boleto.numero} ha sido aprobado. QR disponible.",
                boleto=boleto
            )
            
        else:
            boleto.estado = 'D'
            boleto.participante = None
            boleto.fecha_venta = None
            boleto.save()
            
            # Eliminar QR si existe
            if hasattr(boleto, 'qr'):
                boleto.qr.delete()
            
            Notificacion.objects.create(
                participante=form.instance.boleto.participante,
                tipo='RE',
                mensaje=f"Tu comprobante para el boleto {boleto.numero} fue rechazado. Motivo: {form.instance.motivo_rechazo}",
                boleto=boleto
            )
        
        return response
    
def verificar_qr(request, codigo_qr):
    """Endpoint JSON para el escáner QR del panel admin."""
    try:
        qr = QRBoleto.objects.get(codigo=codigo_qr, activo=True)
        boleto = qr.boleto
        
        data = {
            'valido': True,
            'numero': boleto.numero,
            'rifa': {
                'id': boleto.rifa.id,
                'nombre': boleto.rifa.nombre,
                'fecha_sorteo': timezone.localtime(boleto.rifa.fecha_sorteo).strftime(
                    '%Y-%m-%d %H:%M'
                ),
            },
            'participante': {
                'nombre': boleto.participante.nombre_completo,
                'telefono': boleto.participante.telefono
            },
            'fecha_compra': (
                timezone.localtime(boleto.fecha_venta).strftime('%Y-%m-%d %H:%M')
                if boleto.fecha_venta
                else ''
            ),
            'qr_fecha_generacion': timezone.localtime(qr.fecha_generacion).strftime(
                '%Y-%m-%d %H:%M'
            ),
        }
        
        return JsonResponse(data)
    except QRBoleto.DoesNotExist:
        return JsonResponse({'valido': False}, status=404)


MESES_ES = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
    7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
}

def verificar_boleto_publico(request, codigo_qr):
    """Página pública HTML para verificar boletos escaneando el QR."""
    try:
        qr = QRBoleto.objects.select_related(
            'boleto', 'boleto__rifa', 'boleto__participante'
        ).get(codigo=codigo_qr, activo=True)
        boleto = qr.boleto
        rifa = boleto.rifa
        participante = boleto.participante
        # Con USE_TZ=True, en BD las fechas son UTC; para mostrar en México hay que pasar a TIME_ZONE.
        fecha = timezone.localtime(rifa.fecha_sorteo)
        fecha_sorteo_texto = f"{fecha.day} de {MESES_ES.get(fecha.month, '')} de {fecha.year}"

        fecha_compra_texto = ''
        if boleto.fecha_venta:
            fv = timezone.localtime(boleto.fecha_venta)
            fecha_compra_texto = f"{fv.day} de {MESES_ES.get(fv.month, '')} de {fv.year}"

        context = {
            'boleto': boleto,
            'rifa': rifa,
            'participante': participante,
            'qr': qr,
            'fecha_sorteo_texto': fecha_sorteo_texto,
            'fecha_compra_texto': fecha_compra_texto,
        }
    except QRBoleto.DoesNotExist:
        context = {'boleto': None}

    return render(request, 'rifas/verificar_boleto.html', context)


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            # Redirigir según el tipo de usuario
            if user.is_staff:
                return redirect('rifas:admin_dashboard')
            return redirect('rifas:listado_rifas')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'rifas/login.html')

def logout_view(request):
    logout(request)
    return redirect('rifas:listado_rifas')

import zipfile

def descargar_qrs_aprobados(request):
    # Verificar permisos
    if not request.user.is_staff:
        return HttpResponse('No autorizado', status=403)
    
    # Obtener boletos vendidos y aprobados
    boletos = Boleto.objects.filter(
        estado='V',  # Vendidos
    ).select_related('qr').exclude(qr__imagen_qr='')
    
    if not boletos.exists():
        return HttpResponse('No hay QR para descargar', status=404)
    
    # Crear ZIP en memoria
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for boleto in boletos:
            if boleto.qr and boleto.qr.imagen_qr:
                file_path = boleto.qr.imagen_qr.path
                if os.path.exists(file_path):
                    arcname = f"boleto_{boleto.rifa.nombre}_{boleto.numero}.png"
                    zipf.write(file_path, arcname)
    
    buffer.seek(0)
    
    # Configurar respuesta
    response = HttpResponse(buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="qrs_aprobados.zip"'
    return response

class AdminGestionBoletosView(StaffRequiredMixin, ListView):
    template_name = 'rifas/admin/gestion_boletos.html'
    context_object_name = 'boletos'
    paginate_by = 50  # 50 boletos por página para mejor rendimiento
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_queryset(self):
        rifa_id = self.kwargs.get('rifa_id')
        self.rifa = get_object_or_404(Rifa, pk=rifa_id)
        
        # Base query optimizada
        boletos = Boleto.objects.filter(rifa_id=rifa_id).select_related(
            'participante', 'rifa'
        ).prefetch_related('qr')
        
        # Filtros
        estado = self.request.GET.get('estado')
        if estado:
            boletos = boletos.filter(estado=estado)
        
        numero_inicio = self.request.GET.get('inicio')
        numero_fin = self.request.GET.get('fin')
        if numero_inicio and numero_fin:
            boletos = boletos.filter(numero__gte=numero_inicio, numero__lte=numero_fin)
        
        # Búsqueda por número o participante
        search = self.request.GET.get('search')
        if search:
            boletos = boletos.filter(
                Q(numero__icontains=search) |
                Q(participante__nombre_completo__icontains=search) |
                Q(participante__telefono__icontains=search)
            )
        
        return boletos.order_by('numero')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rifa = self.rifa
        
        # Estadísticas de la rifa
        total_boletos = rifa.boletos_total
        boletos_vendidos = rifa.boletos.filter(estado='V').count()
        boletos_reservados = rifa.boletos.filter(estado='R').count()
        boletos_disponibles = rifa.boletos.filter(estado='D').count()
        boletos_validacion = rifa.boletos.filter(estado='E').count()
        
        # Porcentajes
        porcentaje_vendidos = (boletos_vendidos / total_boletos * 100) if total_boletos > 0 else 0
        porcentaje_reservados = (boletos_reservados / total_boletos * 100) if total_boletos > 0 else 0
        porcentaje_disponibles = (boletos_disponibles / total_boletos * 100) if total_boletos > 0 else 0
        
        context.update({
            'rifa': rifa,
            'total_boletos': total_boletos,
            'boletos_vendidos': boletos_vendidos,
            'boletos_reservados': boletos_reservados,
            'boletos_disponibles': boletos_disponibles,
            'boletos_validacion': boletos_validacion,
            'porcentaje_vendidos': round(porcentaje_vendidos, 1),
            'porcentaje_reservados': round(porcentaje_reservados, 1),
            'porcentaje_disponibles': round(porcentaje_disponibles, 1),
            'participante_form': RegistroParticipanteForm(),
            'comprobante_form': SubirComprobanteForm(),
            'current_estado': self.request.GET.get('estado', ''),
            'current_search': self.request.GET.get('search', ''),
            'current_inicio': self.request.GET.get('inicio', ''),
            'current_fin': self.request.GET.get('fin', ''),
        })
        
        return context
    
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     rifa_id = self.kwargs.get('rifa_id')
    #     context['rifa'] = get_object_or_404(Rifa, pk=rifa_id)
        
    #     # Filtros adicionales
    #     numero_inicio = self.request.GET.get('inicio')
    #     numero_fin = self.request.GET.get('fin')
        
    #     # Base query
    #     boletos = Boleto.objects.filter(rifa_id=rifa_id)
        
    #     # Aplicar filtros si existen
    #     if numero_inicio and numero_fin:
    #         boletos = boletos.filter(numero__gte=numero_inicio, numero__lte=numero_fin)
        
    #     context['boletos'] = boletos.order_by('numero')
    #     context['participante_form'] = RegistroParticipanteForm()
    #     context['comprobante_form'] = SubirComprobanteForm()
        
    #     return context
    
@method_decorator(staff_member_required, name='dispatch')
class AdminAsignarBoletoView(StaffRequiredMixin, View):
    def test_func(self):
        return self.request.user.is_staff
    
    def post(self, request, *args, **kwargs):
        try:
            # Procesar FormData
            boleto_id = request.POST.get('boleto_id')
            participante_nombre = request.POST.get('participante[nombre]')
            participante_direccion = request.POST.get('participante[direccion]')
            participante_telefono = request.POST.get('participante[telefono]')
            
            # Validación básica
            if not all([boleto_id, participante_nombre, participante_telefono]):
                return JsonResponse({'error': 'Datos incompletos'}, status=400)
            
            # Validar que el teléfono tenga exactamente 10 dígitos
            import re
            # Remover espacios, guiones y otros caracteres no numéricos
            telefono_limpio = re.sub(r'\D', '', participante_telefono)
            if len(telefono_limpio) != 10:
                return JsonResponse({'error': 'El teléfono debe tener exactamente 10 dígitos'}, status=400)
            participante_telefono = telefono_limpio
            
            # Procesar boleto y participante
            boleto = get_object_or_404(Boleto, pk=boleto_id)
            
            participante = Participante.objects.create(
                direccion=participante_direccion,
                nombre_completo=participante_nombre,
                telefono=participante_telefono
            )
            
            # Actualizar boleto
            boleto.participante = participante
            boleto.estado = 'V'
            boleto.fecha_venta = timezone.now()
            boleto.vendido_por = request.user
            boleto.save()
            
            # Procesar comprobante si existe
            if 'comprobante[archivo]' in request.FILES:
                comprobante = ComprobantePago(
                    boleto=boleto,
                    imagen=request.FILES['comprobante[archivo]'],
                    #monto=request.POST.get('comprobante[monto]'),
                    #metodo_pago=request.POST.get('comprobante[metodo_pago]'),
                    estado='A',
                    revisado_por=request.user,
                    fecha_revision=timezone.now()
                )
                comprobante.save()
            
            # Generar QR y boleto completo
            qr_instance, created = QRBoleto.objects.get_or_create(
                boleto=boleto,
                defaults={'codigo': str(uuid.uuid4())}
            )
            # Generar la imagen completa del boleto (incluye QR)
            if generar_qr_boleto(qr_instance):
                logger.info(f"Boleto {boleto.numero} generado exitosamente")
            else:
                logger.error(f"Error al generar boleto {boleto.numero}")
            
            return JsonResponse({
                'success': True,
                'message': 'Boleto asignado correctamente'
            })
            
        except Exception as e:
            logger.error(f"Error en asignación: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(staff_member_required, name='dispatch')
class AdminAsignarBoletosMasivoView(StaffRequiredMixin, View):
    """Asigna el mismo participante y comprobante (opcional) a un rango de números de boleto."""

    MAX_BOLETOS_POR_LOTE = 300

    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, *args, **kwargs):
        import re

        try:
            rifa_id = request.POST.get('rifa_id')
            raw_inicio = request.POST.get('numero_inicio')
            raw_fin = request.POST.get('numero_fin')
            participante_nombre = request.POST.get('participante[nombre]')
            participante_direccion = request.POST.get('participante[direccion]')
            participante_telefono = request.POST.get('participante[telefono]')

            if not all([rifa_id, raw_inicio, raw_fin, participante_nombre, participante_telefono]):
                return JsonResponse({'error': 'Datos incompletos'}, status=400)

            try:
                numero_inicio = int(raw_inicio)
                numero_fin = int(raw_fin)
            except (TypeError, ValueError):
                return JsonResponse({'error': 'Rango de números inválido'}, status=400)

            if numero_inicio > numero_fin:
                numero_inicio, numero_fin = numero_fin, numero_inicio

            cantidad = numero_fin - numero_inicio + 1
            if cantidad > self.MAX_BOLETOS_POR_LOTE:
                return JsonResponse(
                    {
                        'error': (
                            f'El rango supera el máximo permitido '
                            f'({self.MAX_BOLETOS_POR_LOTE} boletos por operación).'
                        )
                    },
                    status=400,
                )

            telefono_limpio = re.sub(r'\D', '', participante_telefono)
            if len(telefono_limpio) != 10:
                return JsonResponse({'error': 'El teléfono debe tener exactamente 10 dígitos'}, status=400)

            rifa = get_object_or_404(Rifa, pk=rifa_id)
            esperados = set(range(numero_inicio, numero_fin + 1))

            with transaction.atomic():
                boletos = list(
                    Boleto.objects.select_for_update()
                    .filter(rifa_id=rifa.pk, numero__gte=numero_inicio, numero__lte=numero_fin)
                    .order_by('numero')
                )
                encontrados = {b.numero for b in boletos}
                if len(encontrados) != len(esperados):
                    faltantes = sorted(esperados - encontrados)
                    return JsonResponse(
                        {
                            'error': (
                                'No existen todos los números en esta rifa. '
                                f'Faltan: {faltantes[:30]}'
                                + ('…' if len(faltantes) > 30 else '')
                            )
                        },
                        status=400,
                    )

                no_asignables = [b.numero for b in boletos if b.estado not in ('D', 'R')]
                if no_asignables:
                    return JsonResponse(
                        {
                            'error': (
                                'Solo se pueden asignar boletos disponibles o reservados. '
                                f'No aplican: {no_asignables[:40]}'
                                + ('…' if len(no_asignables) > 40 else '')
                            )
                        },
                        status=400,
                    )

                participante = Participante.objects.create(
                    direccion=participante_direccion,
                    nombre_completo=participante_nombre,
                    telefono=telefono_limpio,
                )

                archivo = request.FILES.get('comprobante[archivo]')
                fecha_venta = timezone.now()
                lote_masivo = None
                if len(boletos) >= 10:
                    lote_masivo = LoteBoletosMasivo.objects.create(
                        rifa=rifa,
                        participante=participante,
                        creado_por=request.user,
                        total_boletos=len(boletos),
                    )

                for boleto in boletos:
                    boleto.participante = participante
                    boleto.estado = 'V'
                    boleto.fecha_venta = fecha_venta
                    boleto.vendido_por = request.user
                    boleto.lote_masivo = lote_masivo
                    boleto.save()

                    if archivo:
                        archivo.seek(0)
                        comprobante = ComprobantePago(
                            boleto=boleto,
                            imagen=archivo,
                            estado='A',
                            revisado_por=request.user,
                            fecha_revision=fecha_venta,
                        )
                        comprobante.save()

                # Crear registros QR faltantes en lote (rápido y sin bloqueo prolongado).
                boletos_ids = [b.id for b in boletos]
                qr_existentes_ids = set(
                    QRBoleto.objects.filter(boleto_id__in=boletos_ids).values_list('boleto_id', flat=True)
                )
                qr_por_crear = [
                    QRBoleto(boleto_id=b_id, codigo=str(uuid.uuid4()))
                    for b_id in boletos_ids
                    if b_id not in qr_existentes_ids
                ]
                if qr_por_crear:
                    QRBoleto.objects.bulk_create(qr_por_crear)

                # Importante: aquí NO se generan imágenes QR.
                # Solo se deja el registro QR (UUID) para generarlo después con "QR masivo".
                qrs_generados = 0

            payload = {
                'success': True,
                'message': (
                    f'Se asignaron {len(boletos)} boletos correctamente. '
                    + 'Aún no se generaron imágenes QR; puedes generarlas desde "QR masivo".'
                ),
                'asignados': len(boletos),
                'qrs_generados': qrs_generados,
            }
            if lote_masivo:
                link_descarga = request.build_absolute_uri(
                    reverse('rifas:boletos_descarga_publica', args=[lote_masivo.token])
                )
                payload.update(
                    {
                        'lote_token': str(lote_masivo.token),
                        'link_descarga': link_descarga,
                        'pdf_descarga': request.build_absolute_uri(
                            reverse('rifas:boletos_descarga_pdf', args=[lote_masivo.token])
                        ),
                    }
                )
            return JsonResponse(payload)

        except Exception as e:
            logger.error(f"Error en asignación masiva: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def reservar_boleto(request, boleto_id):
    try:
        boleto = Boleto.objects.get(pk=boleto_id)
        
        # Verificar que el boleto está disponible
        if boleto.estado != 'D':
            return JsonResponse({
                'success': False,
                'error': 'Este boleto no está disponible para reserva'
            }, status=400)
        
        # Reservar el boleto
        boleto.estado = 'R'
        boleto.fecha_reserva = timezone.now()
        boleto.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Boleto reservado exitosamente',
            'boleto_id': boleto.id,
            'numero': boleto.numero
        })
        
    except Boleto.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Boleto no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def reservar_boletos_masivo(request):
    """
    Reserva todos los boletos disponibles (estado D) en un rango de números de la rifa.
    Misma regla que reservar_boleto: solo aplica a boletos disponibles.
    """
    MAX_BOLETOS = 300
    try:
        rifa_id = request.POST.get('rifa_id')
        raw_inicio = request.POST.get('numero_inicio')
        raw_fin = request.POST.get('numero_fin')

        if not all([rifa_id, raw_inicio, raw_fin]):
            return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)

        try:
            numero_inicio = int(raw_inicio)
            numero_fin = int(raw_fin)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Rango de números inválido'}, status=400)

        if numero_inicio > numero_fin:
            numero_inicio, numero_fin = numero_fin, numero_inicio

        cantidad = numero_fin - numero_inicio + 1
        if cantidad > MAX_BOLETOS:
            return JsonResponse(
                {
                    'success': False,
                    'error': f'El rango supera el máximo permitido ({MAX_BOLETOS} boletos por operación).',
                },
                status=400,
            )

        rifa = get_object_or_404(Rifa, pk=rifa_id)
        esperados = set(range(numero_inicio, numero_fin + 1))

        with transaction.atomic():
            boletos = list(
                Boleto.objects.select_for_update()
                .filter(rifa_id=rifa.pk, numero__gte=numero_inicio, numero__lte=numero_fin)
                .order_by('numero')
            )
            encontrados = {b.numero for b in boletos}
            if len(encontrados) != len(esperados):
                faltantes = sorted(esperados - encontrados)
                return JsonResponse(
                    {
                        'success': False,
                        'error': (
                            'No existen todos los números en esta rifa. '
                            f'Faltan: {faltantes[:30]}' + ('…' if len(faltantes) > 30 else '')
                        ),
                    },
                    status=400,
                )

            no_disponibles = [b.numero for b in boletos if b.estado != 'D']
            if no_disponibles:
                return JsonResponse(
                    {
                        'success': False,
                        'error': (
                            'Solo se pueden reservar boletos en estado disponible. '
                            f'No aplican: {no_disponibles[:40]}'
                            + ('…' if len(no_disponibles) > 40 else '')
                        ),
                    },
                    status=400,
                )

            ahora = timezone.now()
            for boleto in boletos:
                boleto.estado = 'R'
                boleto.fecha_reserva = ahora
                boleto.save()

        return JsonResponse(
            {
                'success': True,
                'message': f'Se reservaron {len(boletos)} boletos correctamente',
                'reservados': len(boletos),
            }
        )

    except Exception as e:
        logger.error(f'Error en reserva masiva: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def generar_qr_boletos_masivo(request):
    """
    Genera QR (registro + imagen) para boletos ya vendidos dentro de un rango.
    No modifica datos de venta, solo completa QR faltante o sin imagen.
    """
    MAX_BOLETOS = 300
    try:
        rifa_id = request.POST.get('rifa_id')
        raw_inicio = request.POST.get('numero_inicio')
        raw_fin = request.POST.get('numero_fin')

        if not all([rifa_id, raw_inicio, raw_fin]):
            return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)

        try:
            numero_inicio = int(raw_inicio)
            numero_fin = int(raw_fin)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Rango de números inválido'}, status=400)

        if numero_inicio > numero_fin:
            numero_inicio, numero_fin = numero_fin, numero_inicio

        cantidad = numero_fin - numero_inicio + 1
        if cantidad > MAX_BOLETOS:
            return JsonResponse(
                {
                    'success': False,
                    'error': f'El rango supera el máximo permitido ({MAX_BOLETOS} boletos por operación).',
                },
                status=400,
            )

        rifa = get_object_or_404(Rifa, pk=rifa_id)
        boletos = list(
            Boleto.objects.filter(
                rifa_id=rifa.pk,
                numero__gte=numero_inicio,
                numero__lte=numero_fin,
                estado='V',
            ).order_by('numero')
        )
        if not boletos:
            return JsonResponse(
                {'success': False, 'error': 'No hay boletos vendidos en ese rango para generar QR.'},
                status=400,
            )

        boletos_ids = [b.id for b in boletos]
        qr_existentes_ids = set(
            QRBoleto.objects.filter(boleto_id__in=boletos_ids).values_list('boleto_id', flat=True)
        )
        qr_por_crear = [
            QRBoleto(boleto_id=b_id, codigo=str(uuid.uuid4()))
            for b_id in boletos_ids
            if b_id not in qr_existentes_ids
        ]
        if qr_por_crear:
            QRBoleto.objects.bulk_create(qr_por_crear)

        qrs = QRBoleto.objects.filter(boleto_id__in=boletos_ids).select_related('boleto')
        generados_ok = 0
        generados_error = 0
        ya_existian = 0

        for qr in qrs:
            if qr.imagen_qr:
                ya_existian += 1
                continue
            if generar_qr_boleto(qr):
                generados_ok += 1
            else:
                generados_error += 1

        return JsonResponse(
            {
                'success': True,
                'message': (
                    f'Proceso completado en rango #{numero_inicio}-#{numero_fin}. '
                    f'Nuevos QR: {generados_ok}, ya existentes: {ya_existian}, errores: {generados_error}.'
                ),
                'total_vendidos_en_rango': len(boletos),
                'qrs_generados': generados_ok,
                'qrs_ya_existian': ya_existian,
                'qrs_error': generados_error,
            }
        )
    except Exception as e:
        logger.error(f'Error en generación masiva de QR: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def editar_boleto_vendido(request, boleto_id):
    """
    Permite editar datos del participante de un boleto vendido
    solo si aún NO tiene imagen QR generada.
    """
    import re

    try:
        with transaction.atomic():
            boleto = get_object_or_404(
                Boleto.objects.select_for_update().select_related('rifa'),
                pk=boleto_id,
                estado='V',
            )

            qr = getattr(boleto, 'qr', None)
            if qr and qr.imagen_qr:
                return JsonResponse(
                    {
                        'success': False,
                        'error': 'No se puede editar: este boleto ya tiene QR generado.',
                    },
                    status=400,
                )

            nombre = (request.POST.get('participante[nombre]') or '').strip()
            direccion = (request.POST.get('participante[direccion]') or '').strip()
            telefono_raw = (request.POST.get('participante[telefono]') or '').strip()
            email = (request.POST.get('participante[email]') or '').strip()

            if not nombre or not telefono_raw:
                return JsonResponse(
                    {'success': False, 'error': 'Nombre y teléfono son obligatorios.'},
                    status=400,
                )

            telefono = re.sub(r'\D', '', telefono_raw)
            if len(telefono) != 10:
                return JsonResponse(
                    {'success': False, 'error': 'El teléfono debe tener exactamente 10 dígitos.'},
                    status=400,
                )

            # Edición individual: crear/usar un participante propio para este boleto.
            # Así evitamos modificar en cascada otros boletos que compartan participante.
            participante_actual = boleto.participante
            if participante_actual and participante_actual.boletos.exclude(pk=boleto.pk).exists():
                participante = Participante.objects.create(
                    nombre_completo=nombre,
                    direccion=direccion,
                    telefono=telefono,
                    email=email or None,
                )
            else:
                participante = participante_actual or Participante()
                participante.nombre_completo = nombre
                participante.direccion = direccion
                participante.telefono = telefono
                participante.email = email or None
                participante.save()

            boleto.participante = participante
            boleto.save(update_fields=['participante'])

        return JsonResponse(
            {
                'success': True,
                'message': f'Boleto #{boleto.numero} actualizado correctamente.',
            }
        )
    except Http404:
        return JsonResponse(
            {'success': False, 'error': 'Boleto no encontrado o no está vendido.'},
            status=404,
        )
    except Exception as e:
        logger.exception('Error al editar boleto vendido')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def generar_qr_boleto_vendido(request, boleto_id):
    """
    Genera el QR (imagen) de un boleto vendido de forma individual.
    """
    try:
        boleto = get_object_or_404(Boleto.objects.select_related('rifa'), pk=boleto_id, estado='V')

        qr, _created = QRBoleto.objects.get_or_create(
            boleto=boleto,
            defaults={'codigo': str(uuid.uuid4())},
        )

        if qr.imagen_qr:
            return JsonResponse(
                {
                    'success': False,
                    'error': f'El boleto #{boleto.numero} ya tiene QR generado.',
                },
                status=400,
            )

        if generar_qr_boleto(qr):
            return JsonResponse(
                {
                    'success': True,
                    'message': f'QR generado correctamente para boleto #{boleto.numero}.',
                }
            )
        return JsonResponse(
            {'success': False, 'error': 'No se pudo generar el QR para este boleto.'},
            status=500,
        )

    except Http404:
        return JsonResponse(
            {'success': False, 'error': 'Boleto no encontrado o no está vendido.'},
            status=404,
        )
    except Exception as e:
        logger.exception('Error al generar QR individual')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)  # Solo para staff/admin
def liberar_boleto(request, boleto_id):
    try:
        boleto = Boleto.objects.get(pk=boleto_id, estado='R')
        
        # Liberar el boleto
        boleto.estado = 'D'
        boleto.participante = None
        boleto.fecha_reserva = None
        boleto.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Boleto liberado exitosamente',
            'boleto_id': boleto.id,
            'nuevo_estado': 'Disponible'
        })
        
    except Boleto.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Boleto no encontrado o no está reservado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def _usuario_puede_liberar_boleto_vendido(user):
    return user.is_authenticated and user.username == 'eramos'


@require_POST
@login_required
@user_passes_test(_usuario_puede_liberar_boleto_vendido)
def liberar_boleto_vendido(request, boleto_id):
    """
    Devuelve un boleto vendido a disponible (solo usuario 'eramos').
    Elimina comprobante y QR asociados.
    """
    try:
        with transaction.atomic():
            boleto = get_object_or_404(
                Boleto.objects.select_for_update(),
                pk=boleto_id,
                estado='V',
            )
            ComprobantePago.objects.filter(boleto=boleto).delete()
            QRBoleto.objects.filter(boleto=boleto).delete()
            boleto.estado = 'D'
            boleto.participante = None
            boleto.fecha_reserva = None
            boleto.fecha_venta = None
            boleto.vendido_por = None
            boleto.save()

        return JsonResponse({
            'success': True,
            'message': 'Boleto liberado y reseteado correctamente',
            'boleto_id': boleto.id,
            'nuevo_estado': 'Disponible',
        })
    except Http404:
        return JsonResponse(
            {
                'success': False,
                'error': 'Boleto no encontrado o no está vendido',
            },
            status=404,
        )
    except Exception as e:
        logger.exception('Error al liberar boleto vendido')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== PANEL DE ADMINISTRACIÓN ====================

@method_decorator(staff_member_required, name='dispatch')
# Modificado: 2026-03-17 22:10:50 - Vista del dashboard admin con estadísticas
class AdminDashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'rifas/admin/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas generales
        total_rifas = Rifa.objects.count()
        rifas_activas = Rifa.objects.filter(activa=True).count()
        total_boletos = Boleto.objects.count()
        boletos_vendidos = Boleto.objects.filter(estado='V').count()
        boletos_reservados = Boleto.objects.filter(estado='R').count()
        boletos_disponibles = Boleto.objects.filter(estado='D').count()
        comprobantes_pendientes = ComprobantePago.objects.filter(estado='P').count()
        
        # Rifas recientes
        rifas_recientes = Rifa.objects.order_by('-fecha_creacion')[:5]
        
        # Rifas con más ventas
        rifas_populares = Rifa.objects.annotate(
            vendidos_count=Count('boletos', filter=Q(boletos__estado='V'))
        ).order_by('-vendidos_count')[:5]
        
        context.update({
            'total_rifas': total_rifas,
            'rifas_activas': rifas_activas,
            'total_boletos': total_boletos,
            'boletos_vendidos': boletos_vendidos,
            'boletos_reservados': boletos_reservados,
            'boletos_disponibles': boletos_disponibles,
            'comprobantes_pendientes': comprobantes_pendientes,
            'rifas_recientes': rifas_recientes,
            'rifas_populares': rifas_populares,
        })
        
        return context


@method_decorator(staff_member_required, name='dispatch')
class AdminMisVentasView(StaffRequiredMixin, TemplateView):
    template_name = 'rifas/admin/mis_ventas.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        mis_boletos = Boleto.objects.filter(
            vendido_por=user, estado='V'
        ).select_related('rifa', 'participante').order_by('-fecha_venta')

        total_vendidos = mis_boletos.count()

        ventas_por_rifa = {}
        for boleto in mis_boletos:
            rifa_nombre = boleto.rifa.nombre
            if rifa_nombre not in ventas_por_rifa:
                ventas_por_rifa[rifa_nombre] = {
                    'rifa': boleto.rifa,
                    'boletos': [],
                    'count': 0,
                    'total': 0,
                }
            ventas_por_rifa[rifa_nombre]['boletos'].append(boleto)
            ventas_por_rifa[rifa_nombre]['count'] += 1
            ventas_por_rifa[rifa_nombre]['total'] += float(boleto.rifa.precio_boleto)

        total_ingresos = sum(v['total'] for v in ventas_por_rifa.values())

        context.update({
            'mis_boletos': mis_boletos,
            'total_vendidos': total_vendidos,
            'total_ingresos': total_ingresos,
            'ventas_por_rifa': ventas_por_rifa,
        })
        return context


class AdminRifasListView(StaffRequiredMixin, ListView):
    model = Rifa
    template_name = 'rifas/admin/rifas_list.html'
    context_object_name = 'rifas'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Rifa.objects.all().annotate(
            vendidos_count=Count('boletos', filter=Q(boletos__estado='V')),
            reservados_count=Count('boletos', filter=Q(boletos__estado='R')),
            disponibles_count=Count('boletos', filter=Q(boletos__estado='D'))
        )
        
        # Filtros
        activa = self.request.GET.get('activa')
        if activa is not None:
            queryset = queryset.filter(activa=activa == 'true')
        
        # Búsqueda
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) | 
                Q(descripcion__icontains=search)
            )
        
        return queryset.order_by('-fecha_creacion')

class AdminRifaCreateView(StaffRequiredMixin, CreateView):
    model = Rifa
    form_class = RifaForm
    template_name = 'rifas/admin/rifa_form.html'
    success_url = reverse_lazy('rifas:admin_rifas_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        rifa = self.object
        
        # Crear boletos automáticamente
        boletos_creados = []
        with transaction.atomic():
            for numero in range(1, rifa.boletos_total + 1):
                boleto = Boleto.objects.create(
                    rifa=rifa,
                    numero=numero,
                    estado='D'
                )
                boletos_creados.append(boleto)
        
        messages.success(
            self.request, 
            f'Rifa "{rifa.nombre}" creada exitosamente con {len(boletos_creados)} boletos.'
        )
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nueva Rifa'
        return context

@method_decorator(staff_member_required, name='dispatch')
class AdminRifaUpdateView(StaffRequiredMixin, UpdateView):
    model = Rifa
    form_class = RifaForm
    template_name = 'rifas/admin/rifa_form.html'
    success_url = reverse_lazy('rifas:admin_rifas_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Rifa "{form.instance.nombre}" actualizada exitosamente.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Rifa: {self.object.nombre}'
        return context

class AdminRifaDetailView(StaffRequiredMixin, DetailView):
    model = Rifa
    template_name = 'rifas/admin/rifa_detail.html'
    context_object_name = 'rifa'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rifa = self.object
        
        # Estadísticas de la rifa
        boletos_vendidos = rifa.boletos.filter(estado='V').count()
        boletos_reservados = rifa.boletos.filter(estado='R').count()
        boletos_disponibles = rifa.boletos.filter(estado='D').count()
        boletos_validacion = rifa.boletos.filter(estado='E').count()
        
        # Ingresos estimados
        ingresos_totales = boletos_vendidos * rifa.precio_boleto
        
        # Comprobantes pendientes de esta rifa
        comprobantes_pendientes = ComprobantePago.objects.filter(
            boleto__rifa=rifa,
            estado='P'
        ).count()
        
        context.update({
            'boletos_vendidos': boletos_vendidos,
            'boletos_reservados': boletos_reservados,
            'boletos_disponibles': boletos_disponibles,
            'boletos_validacion': boletos_validacion,
            'ingresos_totales': ingresos_totales,
            'comprobantes_pendientes': comprobantes_pendientes,
        })
        
        return context

# ==================== GESTIÓN DE USUARIOS ====================

class AdminUsuariosListView(StaffRequiredMixin, ListView):
    model = User
    template_name = 'rifas/admin/usuarios_list.html'
    context_object_name = 'usuarios'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        
        # Filtros
        is_staff = self.request.GET.get('is_staff')
        if is_staff is not None:
            queryset = queryset.filter(is_staff=is_staff == 'true')
        
        is_active = self.request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active == 'true')
        
        # Búsqueda
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | 
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_usuarios'] = User.objects.count()
        context['usuarios_staff'] = User.objects.filter(is_staff=True).count()
        context['usuarios_activos'] = User.objects.filter(is_active=True).count()
        return context

class AdminUsuarioCreateView(StaffRequiredMixin, CreateView):
    model = User
    form_class = UsuarioCreateForm
    template_name = 'rifas/admin/usuario_form.html'
    success_url = reverse_lazy('rifas:admin_usuarios_list')
    
    def test_func(self):
        return self.request.user.is_staff
    
    def form_valid(self, form):
        messages.success(self.request, f'Usuario "{form.instance.username}" creado exitosamente.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Usuario'
        return context

class AdminUsuarioUpdateView(StaffRequiredMixin, UpdateView):
    model = User
    form_class = UsuarioEditForm
    template_name = 'rifas/admin/usuario_form.html'
    success_url = reverse_lazy('rifas:admin_usuarios_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Usuario "{form.instance.username}" actualizado exitosamente.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Usuario: {self.object.username}'
        return context

class AdminUsuarioPasswordView(StaffRequiredMixin, View):
    template_name = 'rifas/admin/usuario_password.html'
    
    def get(self, request, pk):
        usuario = get_object_or_404(User, pk=pk)
        form = UsuarioPasswordForm(user=usuario)
        return render(request, self.template_name, {
            'form': form,
            'usuario': usuario
        })
    
    def post(self, request, pk):
        usuario = get_object_or_404(User, pk=pk)
        form = UsuarioPasswordForm(user=usuario, data=request.POST)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Contraseña de "{usuario.username}" actualizada exitosamente.')
            return redirect('rifas:admin_usuarios_list')
        
        return render(request, self.template_name, {
            'form': form,
            'usuario': usuario
        })

@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_usuario_activo(request, pk):
    """Activa o desactiva un usuario"""
    usuario = get_object_or_404(User, pk=pk)
    
    # No permitir desactivarse a sí mismo
    if usuario == request.user:
        messages.error(request, 'No puedes desactivar tu propia cuenta.')
        return redirect('rifas:admin_usuarios_list')
    
    usuario.is_active = not usuario.is_active
    usuario.save()
    
    estado = 'activado' if usuario.is_active else 'desactivado'
    messages.success(request, f'Usuario "{usuario.username}" {estado} exitosamente.')
    
    return redirect('rifas:admin_usuarios_list')

@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_usuario_staff(request, pk):
    """Convierte un usuario en staff o lo quita"""
    usuario = get_object_or_404(User, pk=pk)
    
    # No permitir quitarse a sí mismo el permiso de staff
    if usuario == request.user:
        messages.error(request, 'No puedes quitar tus propios permisos de administrador.')
        return redirect('rifas:admin_usuarios_list')
    
    usuario.is_staff = not usuario.is_staff
    usuario.save()
    
    estado = 'convertido en administrador' if usuario.is_staff else 'removido como administrador'
    messages.success(request, f'Usuario "{usuario.username}" {estado} exitosamente.')
    
    return redirect('rifas:admin_usuarios_list')


def boletos_descarga_publica(request, token):
    """
    Vista pública para compartir un lote de boletos vendido en asignación masiva.
    """
    lote = get_object_or_404(
        LoteBoletosMasivo.objects.select_related('rifa', 'participante'),
        token=token,
    )
    # Solo mostrar boletos del lote que ya tienen imagen QR generada en storage/qr_codes.
    boletos = list(
        lote.boletos.select_related('qr')
        .filter(
            estado='V',
            qr__imagen_qr__isnull=False,
            qr__imagen_qr__gt='',
            qr__imagen_qr__startswith='qr_codes/',
        )
        .order_by('numero')
    )
    if not boletos:
        return render(
            request,
            'rifas/boletos_descarga_pendiente.html',
            {'lote': lote, 'mensaje': MENSAJE_BOLETOS_DIGITALES_PENDIENTES},
        )

    numero_min = boletos[0].numero
    numero_max = boletos[-1].numero

    return render(
        request,
        'rifas/boletos_descarga_publica.html',
        {
            'lote': lote,
            'boletos': boletos,
            'numero_min': numero_min,
            'numero_max': numero_max,
            'pdf_url': reverse('rifas:boletos_descarga_pdf', args=[lote.token]),
        },
    )


def boletos_descarga_pdf(request, token):
    """
    Descarga en un único PDF todos los boletos de un lote masivo.
    """
    lote = get_object_or_404(
        LoteBoletosMasivo.objects.select_related('rifa', 'participante'),
        token=token,
    )
    boletos = list(
        lote.boletos.select_related('qr')
        .filter(
            estado='V',
            qr__imagen_qr__isnull=False,
            qr__imagen_qr__gt='',
            qr__imagen_qr__startswith='qr_codes/',
        )
        .order_by('numero')
    )
    if not boletos:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        page_w, page_h = A4
        pdf.setFont('Helvetica-Bold', 14)
        pdf.drawString(20 * mm, page_h - 30 * mm, 'Boletos digitales')
        pdf.setFont('Helvetica', 11)
        y = page_h - 48 * mm
        for line in textwrap.wrap(MENSAJE_BOLETOS_DIGITALES_PENDIENTES, width=72):
            pdf.drawString(20 * mm, y, line)
            y -= 6 * mm
        pdf.showPage()
        pdf.save()
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="lote_boletos_{lote.token}.pdf"'
        return response

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4

    # 4 boletos por página en cuadrícula 2×2 (solo imagen, sin texto)
    margin_x = 8 * mm
    margin_y = 8 * mm
    gap_h = 4 * mm
    gap_v = 4 * mm
    usable_w = page_w - 2 * margin_x
    usable_h = page_h - 2 * margin_y
    cell_w = (usable_w - gap_h) / 2
    cell_h = (usable_h - gap_v) / 2

    for i in range(0, len(boletos), 4):
        chunk = boletos[i : i + 4]
        for idx, boleto in enumerate(chunk):
            col = idx % 2
            row = idx // 2
            x0 = margin_x + col * (cell_w + gap_h)
            y_top = page_h - margin_y - row * (cell_h + gap_v)
            _pdf_dibujar_boleto_en_celda(pdf, boleto, x0, y_top, cell_w, cell_h)

        pdf.showPage()

    pdf.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="lote_boletos_{lote.token}.pdf"'
    return response

# Vista protegida para servir archivos de storage
@login_required
@user_passes_test(lambda u: u.is_staff)
def protected_media(request, path):
    """
    Vista protegida para servir archivos de storage.
    Solo usuarios staff pueden acceder a los archivos.
    """
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    
    # Verificar que el archivo existe y está dentro de MEDIA_ROOT
    if not os.path.exists(file_path) or not file_path.startswith(settings.MEDIA_ROOT):
        raise Http404("Archivo no encontrado")
    
    # Verificar que es un archivo (no un directorio)
    if not os.path.isfile(file_path):
        raise Http404("No es un archivo válido")
    
    # Servir el archivo
    return FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')