import uuid
import json
from django.db.models import Q
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST

from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import Rifa, Boleto, Participante, ComprobantePago, QRBoleto, Notificacion
from .forms import (
    RegistroParticipanteForm, 
    SubirComprobanteForm, 
    ValidarComprobanteForm,
    RifasCaptchaForm
)

from .utils import generar_qr_boleto

logger = logging.getLogger(__name__)

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
        context['boletos_disponibles'] = self.object.boletos_disponibles
        context['api_url'] = reverse('rifas:rifa-detail-api', args=[str(self.object.id)])
        return context

class SeleccionNumeroView(LoginRequiredMixin, View):
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
            participante, created = Participante.objects.get_or_create(
                user=request.user,
                defaults={
                    'nombre_completo': request.user.get_full_name(),
                    'telefono': request.user.profile.telefono if hasattr(request.user, 'profile') else '',
                    'email': request.user.email
                }
            )
            
            for boleto in boletos:
                boleto.reservar(participante)
        
        request.session['boletos_reservados'] = [b.id for b in boletos]
        return redirect('rifas:registro_participante')

class RegistroParticipanteView(LoginRequiredMixin, View):
    def get(self, request):
        boletos_ids = request.session.get('boletos_reservados', [])
        if not boletos_ids:
            return redirect('listado_rifas')
        
        boletos = Boleto.objects.filter(id__in=boletos_ids, estado='R')
        form = RegistroParticipanteForm(instance=request.user.participante)
        
        return render(request, 'rifas/registro_participante.html', {
            'form': form,
            'boletos': boletos
        })
    
    def post(self, request):
        boletos_ids = request.session.get('boletos_reservados', [])
        if not boletos_ids:
            return redirect('listado_rifas')
        
        boletos = Boleto.objects.filter(id__in=boletos_ids, estado='R')
        participante = request.user.participante
        form = RegistroParticipanteForm(request.POST, instance=participante)
        
        if form.is_valid():
            form.save()
            
            # Confirmar la compra
            for boleto in boletos:
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

class SubirComprobanteView(LoginRequiredMixin, View):
    def get(self, request, boleto_id):
        boleto = get_object_or_404(Boleto, id=boleto_id, participante__user=request.user, estado='E')
        form = SubirComprobanteForm()
        
        return render(request, 'rifas/subir_comprobante.html', {
            'form': form,
            'boleto': boleto
        })
    
    def post(self, request, boleto_id):
        boleto = get_object_or_404(Boleto, id=boleto_id, participante__user=request.user, estado='E')
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
        boleto = get_object_or_404(Boleto, id=boleto_id, participante__user=request.user, estado='V')
        
        if not hasattr(boleto, 'qr'):
            qr = QRBoleto.objects.create(boleto=boleto)
            qr.imagen_qr = generar_qr_boleto(qr)
            qr.save()
        
        return render(request, 'rifas/mostrar_qr.html', {
            'boleto': boleto
        })

# Vistas de Administración

class ComprobantesPendientesView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ComprobantePago
    template_name = 'rifas/admin/comprobantes_pendientes.html'  # Puedes renombrar este template
    context_object_name = 'comprobantes'
    paginate_by = 20  # Opcional: añade paginación

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        # Filtra comprobantes de boletos VENDIDOS (estado 'V')
        return ComprobantePago.objects.filter(
            Q(boleto__estado='V') | Q(estado='P')  # Boletos vendidos O comprobantes pendientes
        ).select_related(
            'boleto',
            'boleto__participante',
            'boleto__rifa'  # Nuevo: para mostrar info de la rifa
        ).order_by('-fecha_subida')  # Ordena por fecha descendente


@method_decorator(staff_member_required, name='dispatch')
class ValidarComprobanteView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
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
    try:
        qr = QRBoleto.objects.get(codigo=codigo_qr, activo=True)
        boleto = qr.boleto
        
        data = {
            'valido': True,
            'numero': boleto.numero,
            'rifa': {
                'id': boleto.rifa.id,
                'nombre': boleto.rifa.nombre,
                'fecha_sorteo': boleto.rifa.fecha_sorteo.strftime("%Y-%m-%d %H:%M")
            },
            'participante': {
                'nombre': boleto.participante.nombre_completo,
                'telefono': boleto.participante.telefono
            },
            'fecha_compra': boleto.fecha_venta.strftime("%Y-%m-%d %H:%M"),
            'qr_fecha_generacion': qr.fecha_generacion.strftime("%Y-%m-%d %H:%M")
        }
        
        return JsonResponse(data)
    except QRBoleto.DoesNotExist:
        return JsonResponse({'valido': False}, status=404)


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('rifas:listado_rifas')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'rifas/login.html')

def logout_view(request):
    logout(request)
    return redirect('rifas:listado_rifas')

import os
import zipfile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from io import BytesIO
from eventos.models import Boleto

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

@method_decorator(staff_member_required, name='dispatch')
class AdminGestionBoletosView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'rifas/admin/gestion_boletos.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rifa_id = self.kwargs.get('rifa_id')
        context['rifa'] = get_object_or_404(Rifa, pk=rifa_id)
        
        # Filtros adicionales
        numero_inicio = self.request.GET.get('inicio')
        numero_fin = self.request.GET.get('fin')
        
        # Base query con prefetch del QR y participante
        boletos = Boleto.objects.filter(rifa_id=rifa_id).select_related(
            'participante'
        ).prefetch_related(
            'qr'  # Asume que tienes related_name='qr_boleto' en tu modelo QRBoleto
        )
        
        # Aplicar filtros si existen
        if numero_inicio and numero_fin:
            boletos = boletos.filter(numero__gte=numero_inicio, numero__lte=numero_fin)
        
        context['boletos'] = boletos.order_by('numero')
        context['participante_form'] = RegistroParticipanteForm()
        context['comprobante_form'] = SubirComprobanteForm()
        
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
class AdminAsignarBoletoView(LoginRequiredMixin, UserPassesTestMixin, View):
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
            
            # Generar QR
            qr_instance, created = QRBoleto.objects.get_or_create(
                boleto=boleto,
                defaults={'codigo': str(uuid.uuid4())}
            )
            generar_qr_boleto(qr_instance)
            
            return JsonResponse({
                'success': True,
                'message': 'Boleto asignado correctamente'
            })
            
        except Exception as e:
            logger.error(f"Error en asignación: {str(e)}")
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