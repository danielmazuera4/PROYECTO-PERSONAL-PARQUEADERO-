# ============================================================================
# SISTEMA DE GESTIÓN DE PARQUEADERO - VISTAS 
# ============================================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q, F, Case, When, Value
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.urls import reverse
from datetime import datetime, date, timedelta
from io import BytesIO
from decimal import Decimal
import math
import re

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import letter

from .models import Reserva

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

ANCHO_TIRILLA = 80 * mm
# Aumentamos el largo para que las coordenadas (170mm, 150mm, etc) quepan en el papel
LARGO_PAPEL = 200 * mm  

TARIFA_CARRO = 6000
TARIFA_MOTO = 4000

MENSUALIDAD_CARRO = 100000
MENSUALIDAD_MOTO = 80000

EMPRESA_NOMBRE = "PARQUEADERO CENTRAL CALI S.A.S"
EMPRESA_NIT = "901.456.789-0"
EMPRESA_DIRECCION = "Calle 5 # 10-20, Centro, Cali"
EMPRESA_TELEFONO = "(602) 555-1234"


def normalizar_placa(placa):
    return re.sub(r'[^A-Z0-9]', '', placa.strip().upper())


def inferir_tipo_vehiculo(placa):
    # Formato típico Colombia:
    # Carro: ABC123 | Moto: ABC12D
    if re.fullmatch(r'[A-Z]{3}[0-9]{3}', placa):
        return 'CARRO'
    if re.fullmatch(r'[A-Z]{3}[0-9]{2}[A-Z]', placa):
        return 'MOTO'
    return None


def _obtener_historial_admin(fecha_consulta):
    return (
        Reserva.objects.filter(fecha_entrada__date=fecha_consulta)
        .select_related('usuario_registro', 'operario')
        .order_by('-fecha_entrada', '-fecha_salida')
    )


def csrf_failure(request, reason=""):
    referer = request.META.get('HTTP_REFERER')
    messages.warning(
        request,
        "⚠️ La sesión del formulario expiró o cambió. Recarga la página e inténtalo de nuevo.",
    )
    if referer:
        return redirect(referer)
    return redirect(reverse('ingreso'))


def ordenar_por_fecha_descendente(reservas_list):
    """Ordena registros por fecha más reciente primero (fecha_entrada o fecha_salida si es NULL)"""
    return sorted(
        reservas_list,
        key=lambda x: (x.fecha_entrada or x.fecha_salida or timezone.now()),
        reverse=True
    )

# ============================================================================
# FUNCIONES DE GENERACIÓN DE PDFs (TIRILLAS)
# ============================================================================

def generar_ticket_ingreso(reserva):
    buffer = BytesIO()
    # Usamos LARGO_PAPEL para que el encabezado en 170mm sea visible
    p = canvas.Canvas(buffer, pagesize=(ANCHO_TIRILLA, LARGO_PAPEL))

    # Encabezado centrado
    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(ANCHO_TIRILLA/2, 185*mm, EMPRESA_NOMBRE)
    p.setFont("Helvetica", 8)
    p.drawCentredString(ANCHO_TIRILLA/2, 180*mm, f"NIT: {EMPRESA_NIT}")
    p.drawCentredString(ANCHO_TIRILLA/2, 176*mm, EMPRESA_DIRECCION)
    p.drawCentredString(ANCHO_TIRILLA/2, 172*mm, f"Tel: {EMPRESA_TELEFONO}")

    p.line(5*mm, 168*mm, 75*mm, 168*mm)

    # Información del ticket
    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(ANCHO_TIRILLA/2, 162*mm, "TICKET DE INGRESO")
    
    p.setFont("Helvetica", 9)
    p.drawString(10*mm, 152*mm, f"No. Ticket: {str(reserva.id).zfill(8)}")
    
    if reserva.fecha_entrada:
        fecha_local = localtime(reserva.fecha_entrada)
        p.drawString(10*mm, 147*mm, f"Fecha: {fecha_local.strftime('%d/%m/%Y')}")
        p.drawString(10*mm, 142*mm, f"Hora: {fecha_local.strftime('%I:%M %p')}")
    else:
        p.drawString(10*mm, 147*mm, "Fecha: (Sin registro)")
        p.drawString(10*mm, 142*mm, "Hora: (Sin registro)")
    
    # Datos vehículo (En grande para el operario)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(10*mm, 130*mm, f"PLACA: {reserva.placa}")
    p.setFont("Helvetica", 10)
    p.drawString(10*mm, 124*mm, f"Tipo: {reserva.tipo_vehiculo}")
    
    p.line(5*mm, 118*mm, 75*mm, 118*mm)
    
    # Avisos importantes
    p.setFont("Helvetica-Bold", 8)
    p.drawString(10*mm, 110*mm, "IMPORTANTE:")
    p.setFont("Helvetica", 7)
    p.drawString(10*mm, 106*mm, "- Presente este ticket para retirar su vehículo.")
    p.drawString(10*mm, 102*mm, "- Pérdida genera cobro de tarifa plena ($15.000).")
    p.drawString(10*mm, 98*mm, "- No nos hacemos responsables por objetos dejados.")
    
    # Tarifas Informativas
    p.setFont("Helvetica-Bold", 8)
    p.drawString(10*mm, 88*mm, "TARIFAS:")
    p.setFont("Helvetica", 7)
    p.drawString(10*mm, 84*mm, f"Carros: ${TARIFA_CARRO:,} | Motos: ${TARIFA_MOTO:,}")
    
    p.line(5*mm, 78*mm, 75*mm, 78*mm)
    
    # Planes Mensuales
    p.setFont("Helvetica-Bold", 8)
    p.drawCentredString(ANCHO_TIRILLA/2, 72*mm, "PLANES MENSUALES")
    p.setFont("Helvetica", 7)
    p.drawString(10*mm, 68*mm, f"Carros: ${MENSUALIDAD_CARRO:,}")
    p.drawString(10*mm, 64*mm, f"Motos: ${MENSUALIDAD_MOTO:,}")
    
    p.line(5*mm, 58*mm, 75*mm, 58*mm)

    # Pie de página
    p.setFont("Helvetica-Oblique", 8)
    p.drawCentredString(ANCHO_TIRILLA/2, 50*mm, "¡Gracias por su visita!")
    p.setFont("Helvetica", 7)
    p.drawCentredString(ANCHO_TIRILLA/2, 45*mm, "Lunes a Domingo 6:00 AM - 10:00 PM")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


def generar_ticket_salida(reserva):
    buffer = BytesIO()
    # Mantenemos el tamaño de papel que ya definiste como global
    p = canvas.Canvas(buffer, pagesize=(ANCHO_TIRILLA, LARGO_PAPEL))

    # --- ENCABEZADO ---
    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(ANCHO_TIRILLA/2, 185*mm, EMPRESA_NOMBRE)
    p.setFont("Helvetica", 8)
    p.drawCentredString(ANCHO_TIRILLA/2, 180*mm, f"NIT: {EMPRESA_NIT}")
    p.drawCentredString(ANCHO_TIRILLA/2, 176*mm, EMPRESA_DIRECCION)
    
    p.line(5*mm, 172*mm, 75*mm, 172*mm)

    # --- TÍTULO RECIBO ---
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(ANCHO_TIRILLA/2, 165*mm, "RECIBO DE SALIDA")
    
    # --- INFORMACIÓN DEL SERVICIO ---
    p.setFont("Helvetica", 9)
    # Aumentamos el salto de línea entre cada dato (5mm o 6mm es ideal)
    p.drawString(10*mm, 155*mm, f"No. Ticket: {str(reserva.id).zfill(8)}")
    p.drawString(10*mm, 149*mm, f"Placa: {reserva.placa}")
    p.drawString(10*mm, 143*mm, f"Tipo: {reserva.tipo_vehiculo}")
    p.drawString(10*mm, 137*mm, f"Modalidad: {reserva.get_modalidad_display()}")
    operario_nombre = reserva.operario.username if reserva.operario else "---"
    p.drawString(10*mm, 131*mm, f"Operario: {operario_nombre}")
    
    p.line(5*mm, 126*mm, 75*mm, 126*mm)

    # --- TIEMPOS ---
    p.setFont("Helvetica-Bold", 9)
    p.drawString(10*mm, 119*mm, "TIEMPOS:")
    p.setFont("Helvetica", 9)
    
    if reserva.fecha_entrada:
        entrada_local = localtime(reserva.fecha_entrada)
        p.drawString(10*mm, 113*mm, f"Entrada: {entrada_local.strftime('%d/%m/%Y %H:%M')}")
    else:
        p.drawString(10*mm, 113*mm, "Entrada: (Sin registro de entrada)")
    
    if reserva.fecha_salida:
        salida_local = localtime(reserva.fecha_salida)
        p.drawString(10*mm, 107*mm, f"Salida:  {salida_local.strftime('%d/%m/%Y %H:%M')}")
    else:
        p.drawString(10*mm, 107*mm, "Salida: (Sin registro de salida)")

    # --- TOTAL A PAGAR ---
    p.line(5*mm, 99*mm, 75*mm, 99*mm)
    
    p.setFont("Helvetica-Bold", 14)
    # Centralizamos el cobro para que destaque
    p.drawCentredString(ANCHO_TIRILLA/2, 89*mm, f"TOTAL: ${reserva.total_pagar:,.0f} COP")
    
    p.line(5*mm, 82*mm, 75*mm, 82*mm)

    # --- PIE DE PÁGINA ---
    p.setFont("Helvetica-Oblique", 9)
    p.drawCentredString(ANCHO_TIRILLA/2, 74*mm, "¡Vuelva pronto!")
    p.setFont("Helvetica", 7)
    p.drawCentredString(ANCHO_TIRILLA/2, 69*mm, "Gracias por preferirnos")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


def generar_ticket_mensualidad(reserva):
    """Genera comprobante PDF para el pago de mensualidad."""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=(ANCHO_TIRILLA, LARGO_PAPEL))

    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(ANCHO_TIRILLA / 2, 185 * mm, EMPRESA_NOMBRE)
    p.setFont("Helvetica", 8)
    p.drawCentredString(ANCHO_TIRILLA / 2, 180 * mm, f"NIT: {EMPRESA_NIT}")
    p.drawCentredString(ANCHO_TIRILLA / 2, 176 * mm, EMPRESA_DIRECCION)

    p.line(5 * mm, 172 * mm, 75 * mm, 172 * mm)

    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(ANCHO_TIRILLA / 2, 165 * mm, "RECIBO MENSUALIDAD")

    p.setFont("Helvetica", 9)
    p.drawString(10 * mm, 156 * mm, f"No. Recibo: {str(reserva.id).zfill(8)}")
    p.drawString(10 * mm, 150 * mm, f"Placa: {reserva.placa}")
    p.drawString(10 * mm, 144 * mm, f"Tipo: {reserva.tipo_vehiculo}")
    operario_nombre = reserva.operario.username if reserva.operario else "---"
    p.drawString(10 * mm, 138 * mm, f"Operario: {operario_nombre}")

    fecha_ref = reserva.fecha_entrada or timezone.now()
    fecha_ref_local = localtime(fecha_ref)
    p.drawString(10 * mm, 132 * mm, f"Fecha pago: {fecha_ref_local.strftime('%d/%m/%Y %H:%M')}")

    if reserva.fecha_vencimiento:
        venc_local = localtime(reserva.fecha_vencimiento)
        p.drawString(10 * mm, 126 * mm, f"Vence: {venc_local.strftime('%d/%m/%Y')}")
    else:
        p.drawString(10 * mm, 126 * mm, "Vence: ---")

    p.line(5 * mm, 120 * mm, 75 * mm, 120 * mm)

    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(ANCHO_TIRILLA / 2, 110 * mm, f"PAGADO: ${reserva.total_pagar:,.0f} COP")

    p.line(5 * mm, 102 * mm, 75 * mm, 102 * mm)

    p.setFont("Helvetica", 8)
    p.drawCentredString(ANCHO_TIRILLA / 2, 95 * mm, "Comprobante de pago de mensualidad")
    p.setFont("Helvetica-Oblique", 8)
    p.drawCentredString(ANCHO_TIRILLA / 2, 89 * mm, "Gracias por su confianza")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# ============================================================================
# VISTAS PRINCIPALES
# ============================================================================

@login_required
def menu_principal(request):
    if request.user.is_staff:
        return redirect('dashboard_admin')
    return render(request, 'reservas/menu.html')

@login_required
def ingreso(request):
    if request.method == 'GET':
        ticket_ingreso_id = request.session.pop('ticket_ingreso_id', None)
        return render(request, 'reservas/ingreso.html', {'ticket_ingreso_id': ticket_ingreso_id})

    if request.method == 'POST':
        placa = normalizar_placa(request.POST.get('placa', ''))
        tipo_enviado = request.POST.get('tipo', '').strip().upper()
        modalidad = 'DIA_HORA'

        tipo = inferir_tipo_vehiculo(placa)
        if not tipo:
            messages.error(
                request,
                "Formato de placa no reconocido. Usa formato carro (ABC123) o moto (ABC12D).",
            )
            return redirect('ingreso')

        if tipo_enviado and tipo_enviado != tipo:
            messages.error(
                request,
                f"Tipo inválido para la placa {placa}. Según su formato corresponde a {tipo}.",
            )
            return redirect('ingreso')

        # Si la placa tiene mensualidad vigente, no debe ingresar por Día/Hora.
        contrato_vigente = (
            Reserva.objects.filter(
                placa=placa,
                modalidad='MENSUALIDAD',
                fecha_vencimiento__gte=timezone.now(),
            )
            .order_by('-fecha_vencimiento', '-id')
            .first()
        )
        if contrato_vigente:
            dias_restantes = max(0, (contrato_vigente.fecha_vencimiento.date() - timezone.localdate()).days)
            messages.warning(
                request,
                f"⚠️ El vehículo {placa} tiene mensualidad vigente. "
                f"Vence el {localtime(contrato_vigente.fecha_vencimiento).strftime('%d/%m/%Y')} "
                f"(faltan {dias_restantes} día(s)). Dirígete a Gestión de Mensualidades.",
            )
            return redirect('ingreso')
        
        # 1. Validar si ya existe como vehículo activo
        reserva_activa = (
            Reserva.objects.filter(placa=placa, activo=True)
            .order_by('-id')  # ID más reciente
            .first()
        )
        if reserva_activa:
            messages.warning(request, f"⚠️ El vehículo {placa} ya se encuentra ingresado.")
            return redirect('ingreso')
        
        if placa:
            # Registro exclusivo para modalidad Día/Hora
            nueva_reserva = Reserva.objects.create(
                placa=placa,
                tipo_vehiculo=tipo,
                modalidad=modalidad,
                fecha_entrada=timezone.now(),
                total_pagar=Decimal('0.00'),
                usuario_registro=request.user,
                operario=request.user,
            )

            # ==========================================================
            # AQUÍ VA EL MENSAJE DE ÉXITO (MODERNO)
            # ==========================================================
            messages.success(request, f"✅ Registro Exitoso: El vehículo con placa {placa} ha ingresado.")
            # ==========================================================

            # Guardamos el id para abrir el PDF en nueva pestaña solo si fue exitoso.
            request.session['ticket_ingreso_id'] = nueva_reserva.id
            return redirect('ingreso')

    return render(request, 'reservas/ingreso.html', {'ticket_ingreso_id': None})


@login_required
def ticket_ingreso_pdf(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    buffer = generar_ticket_ingreso(reserva)
    return HttpResponse(buffer, content_type='application/pdf')


@login_required
def ticket_mensualidad_pdf(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id, modalidad='MENSUALIDAD', es_pago_mensualidad=True)
    buffer = generar_ticket_mensualidad(reserva)
    return HttpResponse(buffer, content_type='application/pdf')

@login_required
def salida(request):
    reserva = None
    aviso_mensualidad = None
    # Recuperamos el ID de la sesión para el script del PDF
    ticket_salida_id = request.session.pop('ticket_salida_id', None)

    if request.method == 'POST':
        placa_buscar = normalizar_placa(request.POST.get('placa_buscar', ''))
        reserva = Reserva.objects.filter(placa=placa_buscar, activo=True).first()

        if reserva and reserva.modalidad == 'MENSUALIDAD':
            dias_restantes = None
            if reserva.fecha_vencimiento:
                dias_restantes = max(0, (reserva.fecha_vencimiento.date() - timezone.localdate()).days)

            aviso_mensualidad = (
                f"La placa {reserva.placa} tiene una mensualidad activa. "
                f"Dirígete a la vista de mensualidades para gestionarla."
            )
            if dias_restantes is not None:
                aviso_mensualidad = (
                    f"La placa {reserva.placa} tiene una mensualidad activa y vence el "
                    f"{localtime(reserva.fecha_vencimiento).strftime('%d/%m/%Y')} "
                    f"(faltan {dias_restantes} día(s)). Dirígete a la vista de mensualidades para gestionarla."
                )

            return render(request, 'reservas/salida.html', {
                'reserva': None,
                'ticket_salida_id': ticket_salida_id,
                'aviso_mensualidad': aviso_mensualidad,
                'placa_mensualidad': placa_buscar,
            })

        # --- 1. CÁLCULO PREVIO (Para mostrar el precio antes de confirmar) ---
        if reserva and 'confirmar_salida' not in request.POST:
            if reserva.fecha_entrada:  # Verificar que exista fecha_entrada
                if reserva.modalidad == 'DIA_HORA':
                    ahora = timezone.now()
                    duracion = ahora - reserva.fecha_entrada
                    # Cobramos mínimo 1 hora, redondeando hacia arriba
                    horas = max(1, math.ceil(duracion.total_seconds() / 3600))
                    
                    # Definir tarifa según tipo de vehículo
                    tarifa = TARIFA_CARRO if reserva.tipo_vehiculo == 'CARRO' else TARIFA_MOTO
                    
                    # Creamos el atributo temporal para el HTML
                    reserva.total_estimado = horas * tarifa
                else:
                    # Si es mensualidad, el cobro por movimiento es 0
                    reserva.total_estimado = 0
            else:
                # Si no hay fecha_entrada, no calculamos
                reserva.total_estimado = 0

        # Validación si no se encuentra la placa
        if not reserva and 'confirmar_salida' not in request.POST:
            messages.error(request, f"No se encontró un vehículo activo con placa {placa_buscar}.")
            return redirect('salida')

        if reserva and reserva.modalidad == 'MENSUALIDAD' and 'confirmar_salida' in request.POST:
            messages.warning(
                request,
                f"La placa {reserva.placa} tiene una mensualidad activa. Dirígete a la vista de mensualidades para gestionarla."
            )
            return redirect('salida')
        
        # --- 2. PROCESAR SALIDA DEFINITIVA ---
        if 'confirmar_salida' in request.POST and reserva:
            fecha_salida_ahora = timezone.now()
            
            # Calcular cobro solo si existe fecha_entrada
            if reserva.fecha_entrada:
                if reserva.modalidad == 'DIA_HORA':
                    duracion = fecha_salida_ahora - reserva.fecha_entrada
                    horas = max(1, math.ceil(duracion.total_seconds() / 3600))
                    tarifa = TARIFA_CARRO if reserva.tipo_vehiculo == 'CARRO' else TARIFA_MOTO
                    total_cobrado = Decimal(str(horas * tarifa))
                else:
                    total_cobrado = Decimal('0.00')
            else:
                total_cobrado = Decimal('0.00')
            
            # Verificar si el usuario que saca es diferente al que ingresó
            usuario_diferente = reserva.usuario_registro != request.user
            
            if usuario_diferente:
                # Crear registro de SOLO SALIDA (sin fecha_entrada)
                Reserva.objects.create(
                    placa=reserva.placa,
                    tipo_vehiculo=reserva.tipo_vehiculo,
                    modalidad=reserva.modalidad,
                    fecha_entrada=None,  # Registro de solo salida
                    fecha_salida=fecha_salida_ahora,
                    registra_solo_salida=True,
                    total_pagar=total_cobrado,
                    usuario_registro=None,
                    operario=request.user,
                    es_pago_mensualidad=False,
                    activo=False,
                )
                # El registro original NO recibe fecha_salida (queda NULL)
                reserva.activo = False
                # NO asignamos fecha_salida al registro original
            else:
                # Mismo usuario: registro completo con entrada y salida
                reserva.fecha_salida = fecha_salida_ahora
                reserva.total_pagar = total_cobrado
                reserva.activo = False
                reserva.operario = request.user
            
            reserva.save()
            
            messages.success(request, f"✅ Salida Exitosa: El vehículo {reserva.placa} ha salido correctamente.")
            
            # Guardamos el ID en sesión para que el script de JS abra el PDF
            # Si fue solo-salida, usamos el ID del nuevo registro; si no, el original
            if usuario_diferente:
                nuevo_registro = Reserva.objects.filter(
                    placa=reserva.placa,
                    registra_solo_salida=True,
                    fecha_salida__year=fecha_salida_ahora.year,
                    fecha_salida__month=fecha_salida_ahora.month,
                    fecha_salida__day=fecha_salida_ahora.day
                ).first()
                if nuevo_registro:
                    request.session['ticket_salida_id'] = nuevo_registro.id
                else:
                    request.session['ticket_salida_id'] = reserva.id
            else:
                request.session['ticket_salida_id'] = reserva.id
            return redirect('salida')
    
    return render(request, 'reservas/salida.html', {
        'reserva': reserva, 
        'ticket_salida_id': ticket_salida_id,
        'aviso_mensualidad': aviso_mensualidad,
    })

@login_required
def dashboard_admin(request):
    if not request.user.is_staff:
        return redirect('menu_principal')
    
    # CAPTURA LAS FECHAS DEL RANGO
    f_inicio_str = request.GET.get('fecha_inicio')
    f_fin_str = request.GET.get('fecha_fin')
    
    # Por defecto, si no hay filtro, usa el día de hoy
    hoy_local = timezone.localdate()
    fecha_inicio = datetime.strptime(f_inicio_str, '%Y-%m-%d').date() if f_inicio_str else hoy_local
    fecha_fin = datetime.strptime(f_fin_str, '%Y-%m-%d').date() if f_fin_str else hoy_local

    buscar_placa = request.GET.get('buscar_placa', '').strip()
    
    if buscar_placa:
        # Búsqueda por placa: incluir entrada + salida
        placa_normalizada = normalizar_placa(buscar_placa)
        historial = ordenar_por_fecha_descendente(list(
            Reserva.objects.filter(placa=placa_normalizada)
            .select_related('usuario_registro', 'operario')
        ))
    else:
        # Filtramos el historial por el rango de fechas seleccionado
        # Incluye registros con fecha_entrada en rango O registros de solo-salida con fecha_salida en rango
        historial = ordenar_por_fecha_descendente(list(
            Reserva.objects.filter(
                Q(fecha_entrada__date__range=[fecha_inicio, fecha_fin]) |
                Q(registra_solo_salida=True, fecha_salida__date__range=[fecha_inicio, fecha_fin])
            )
            .select_related('usuario_registro', 'operario')
        ))
    
    # Lógica de días restantes de mensualidad
    for movimiento in historial:
        if movimiento.modalidad == 'MENSUALIDAD' and movimiento.fecha_vencimiento:
            movimiento.dias_restantes_mensualidad = (movimiento.fecha_vencimiento.date() - hoy_local).days
            movimiento.dias_vencido_mensualidad = abs(min(movimiento.dias_restantes_mensualidad, 0))
        else:
            movimiento.dias_restantes_mensualidad = None
            movimiento.dias_vencido_mensualidad = None

    # --- TOTALES CALCULADOS POR RANGO ---
    
    # DIA/HORA (Se filtran por fecha de salida dentro del rango)
    base_dia_hora = Reserva.objects.filter(modalidad='DIA_HORA', activo=False, fecha_salida__date__range=[fecha_inicio, fecha_fin])
    
    total_dia_hora = base_dia_hora.aggregate(Sum('total_pagar'))['total_pagar__sum'] or Decimal('0.00')
    total_dia_hora_carro = base_dia_hora.filter(tipo_vehiculo='CARRO').aggregate(Sum('total_pagar'))['total_pagar__sum'] or Decimal('0.00')
    total_dia_hora_moto = base_dia_hora.filter(tipo_vehiculo='MOTO').aggregate(Sum('total_pagar'))['total_pagar__sum'] or Decimal('0.00')

    # MENSUALIDAD (Se filtran por fecha de entrada/pago dentro del rango O solo-salida en rango)
    base_mensual = Reserva.objects.filter(modalidad='MENSUALIDAD').filter(
        Q(fecha_entrada__date__range=[fecha_inicio, fecha_fin]) |
        Q(registra_solo_salida=True, fecha_salida__date__range=[fecha_inicio, fecha_fin])
    )
    
    total_mensualidad = base_mensual.aggregate(Sum('total_pagar'))['total_pagar__sum'] or Decimal('0.00')
    total_mensualidad_carro = base_mensual.filter(tipo_vehiculo='CARRO').aggregate(Sum('total_pagar'))['total_pagar__sum'] or Decimal('0.00')
    total_mensualidad_moto = base_mensual.filter(tipo_vehiculo='MOTO').aggregate(Sum('total_pagar'))['total_pagar__sum'] or Decimal('0.00')

    total_hoy = total_dia_hora + total_mensualidad
    
    context = {
        'total_hoy': total_hoy,
        'total_dia_hora': total_dia_hora,
        'total_mensualidad': total_mensualidad,
        'total_dia_hora_carro': total_dia_hora_carro,
        'total_dia_hora_moto': total_dia_hora_moto,
        'total_mensualidad_carro': total_mensualidad_carro,
        'total_mensualidad_moto': total_mensualidad_moto,
        'carros_activos': Reserva.objects.filter(tipo_vehiculo='CARRO', activo=True).count(),
        'motos_activos': Reserva.objects.filter(tipo_vehiculo='MOTO', activo=True).count(),
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'historial': historial,
        'buscar_placa': buscar_placa
    }
    return render(request, 'reservas/dashboard.html', context)

@login_required
def eliminar_reserva(request, reserva_id):
    if not request.user.is_staff:
        return redirect('menu_principal')
    
    reserva = Reserva.objects.get(id=reserva_id)
    reserva.delete()
    messages.success(request, "Registro eliminado.")
    return redirect('dashboard_admin')

# PDF LISTA VISTA ADMIN - REPORTE DIARIO DE VEHÍCULOS

@login_required
def reporte_diario_pdf(request):
    # 1. CAPTURAMOS EL RANGO (Igual que en el Dashboard)
    f_inicio_str = request.GET.get('fecha_inicio')
    f_fin_str = request.GET.get('fecha_fin')
    
    hoy = timezone.localdate()
    # Convertimos strings a objetos date de Python
    try:
        f_inicio = datetime.strptime(f_inicio_str, '%Y-%m-%d').date() if f_inicio_str else hoy
        f_fin = datetime.strptime(f_fin_str, '%Y-%m-%d').date() if f_fin_str else hoy
    except ValueError:
        f_inicio = f_fin = hoy

    # 2. FILTRAMOS EL HISTORIAL POR EL RANGO
    # Incluye registros con fecha_entrada en rango O registros de solo-salida con fecha_salida en rango
    historial = Reserva.objects.filter(
        Q(fecha_entrada__date__range=[f_inicio, f_fin]) |
        Q(registra_solo_salida=True, fecha_salida__date__range=[f_inicio, f_fin])
    ).select_related('operario').order_by('fecha_entrada', 'fecha_salida')

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    ancho_pagina, alto_pagina = letter

    # --- ENCABEZADO DEL REPORTE ---
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(ancho_pagina/2, alto_pagina - 40, EMPRESA_NOMBRE)
    
    p.setFont("Helvetica-Bold", 11)
    # Título dinámico: Si es un solo día muestra uno, si es rango muestra ambos
    if f_inicio == f_fin:
        texto_fecha = f"REPORTE DE MOVIMIENTOS - {f_inicio.strftime('%d/%m/%Y')}"
    else:
        texto_fecha = f"REPORTE DESDE {f_inicio.strftime('%d/%m/%Y')} HASTA {f_fin.strftime('%d/%m/%Y')}"
    
    p.drawCentredString(ancho_pagina/2, alto_pagina - 60, texto_fecha)
    
    # --- TÍTULOS DE LAS COLUMNAS ---
    y = alto_pagina - 90
    p.setFont("Helvetica-Bold", 9)
    p.drawString(40, y, "FECHA")
    p.drawString(90, y, "PLACA")
    p.drawString(150, y, "TIPO")
    p.drawString(210, y, "MODALIDAD")
    p.drawString(290, y, "ENTRADA")
    p.drawString(360, y, "SALIDA")
    p.drawString(430, y, "OPERARIO")
    p.drawString(520, y, "VALOR")

    p.line(40, y - 5, 560, y - 5)

    # --- LISTADO DE VEHÍCULOS ---
    p.setFont("Helvetica", 9)
    y -= 20
    total_recaudado = 0

    for r in historial:
        # Control de salto de página
        if y < 60:
            p.showPage()
            p.setFont("Helvetica", 9)
            y = alto_pagina - 50

        # Dibujar Datos
        fecha_ref = r.fecha_entrada if r.fecha_entrada else r.fecha_salida
        if fecha_ref:
            p.drawString(40, y, fecha_ref.strftime('%d/%m/%y'))
        else:
            p.drawString(40, y, "N/A")
        
        p.drawString(90, y, r.placa.upper())
        p.drawString(150, y, r.tipo_vehiculo)
        p.drawString(210, y, r.get_modalidad_display()[:15]) # Cortamos si es muy largo
        
        if r.fecha_entrada:
            entrada_local = localtime(r.fecha_entrada).strftime('%I:%M %p')
            p.drawString(290, y, entrada_local)
        else:
            p.drawString(290, y, "---")
        
        if r.fecha_salida:
            salida_local = localtime(r.fecha_salida).strftime('%I:%M %p')
        else:
            salida_local = "En parqueadero"
        p.drawString(360, y, salida_local)

        operario_nombre = r.operario.username if r.operario else "---"
        if len(operario_nombre) > 12:
            operario_nombre = operario_nombre[:12]
        p.drawString(430, y, operario_nombre)
        
        cobro = r.total_pagar if r.total_pagar else 0
        p.drawString(520, y, f"${cobro:,.0f}")
        
        total_recaudado += cobro
        y -= 15 # Espacio entre filas

    # --- RESUMEN FINAL ---
    if y < 100: # Si no cabe el total, pasamos a otra hoja
        p.showPage()
        y = alto_pagina - 50

    p.line(40, y, 560, y)
    y -= 20
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y, "TOTAL RECAUDADO:")
    p.drawRightString(550, y, f"${total_recaudado:,.0f} COP")

    p.showPage()
    p.save()
    buffer.seek(0)
    
    # Nombre de archivo dinámico
    nombre_archivo = f"reporte_{f_inicio}_{f_fin}.pdf"
    return HttpResponse(buffer, content_type='application/pdf', headers={
        'Content-Disposition': f'inline; filename="{nombre_archivo}"'
    })

@login_required
def generar_pdf_salida(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    buffer = generar_ticket_salida(reserva)
    return HttpResponse(buffer, content_type='application/pdf')

@login_required
def generar_reporte_placa_pdf(request):
    """Genera PDF con todos los movimientos de una placa específica"""
    if not request.user.is_staff:
        return redirect('menu_principal')
    
    buscar_placa = request.GET.get('placa', '').strip()
    if not buscar_placa:
        return redirect('dashboard_admin')
    
    placa_normalizada = normalizar_placa(buscar_placa)
    
    # Obtener todos los movimientos de esa placa (sin filtro de fecha)
    movimientos = (
        Reserva.objects.filter(placa=placa_normalizada)
        .annotate(
            fecha_efectiva=Coalesce('fecha_entrada', 'fecha_salida')
        )
        .select_related('usuario_registro', 'operario')
        .order_by('fecha_efectiva')  # Ascendente para reportes (más antiguo primero)
    )
    
    if not movimientos.exists():
        messages.error(request, f"No se encontraron movimientos para la placa {placa_normalizada}")
        return redirect('dashboard_admin')
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    ancho_pagina, alto_pagina = letter
    
    # --- ENCABEZADO DEL REPORTE ---
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(ancho_pagina/2, alto_pagina - 40, EMPRESA_NOMBRE)
    
    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(ancho_pagina/2, alto_pagina - 60, f"HISTORIAL DE PLACA: {placa_normalizada}")
    
    # --- INFO BÁSICA DE LA PLACA ---
    primer_movimiento = movimientos.first()
    p.setFont("Helvetica", 9)
    p.drawString(50, alto_pagina - 80, f"Tipo de Vehículo: {primer_movimiento.tipo_vehiculo}")
    p.drawString(50, alto_pagina - 95, f"Total Movimientos: {movimientos.count()}")
    
    # --- TÍTULOS DE LAS COLUMNAS ---
    y = alto_pagina - 125
    p.setFont("Helvetica-Bold", 9)
    p.drawString(50, y, "FECHA")
    p.drawString(110, y, "ENTRADA")
    p.drawString(170, y, "SALIDA")
    p.drawString(240, y, "MODALIDAD")
    p.drawString(340, y, "OPERARIO")
    p.drawString(460, y, "COBRO")
    
    # Línea debajo de los títulos
    p.line(50, y - 8, 550, y - 8)
    
    # --- CICLO PARA DIBUJAR CADA MOVIMIENTO ---
    p.setFont("Helvetica", 8)
    y -= 22  # Aumentamos espaciado entre encabezado y primer item
    total_recaudado = 0
    
    for movimiento in movimientos:
        # Si llegamos muy abajo, creamos nueva página
        if y < 60:
            p.showPage()
            # Repetir encabezado en nueva página
            p.setFont("Helvetica-Bold", 11)
            p.drawString(50, alto_pagina - 40, EMPRESA_NOMBRE)
            p.drawString(50, alto_pagina - 55, f"HISTORIAL DE PLACA: {placa_normalizada} (continuación)")
            
            y = alto_pagina - 100
            p.setFont("Helvetica-Bold", 9)
            p.drawString(50, y, "FECHA")
            p.drawString(110, y, "ENTRADA")
            p.drawString(170, y, "SALIDA")
            p.drawString(240, y, "MODALIDAD")
            p.drawString(340, y, "OPERARIO")
            p.drawString(460, y, "COBRO")
            p.line(50, y - 8, 550, y - 8)
            y -= 22
            p.setFont("Helvetica", 8)
        
        # Fecha entrada (máx 15 caracteres)
        if movimiento.fecha_entrada:
            fecha_entrada = localtime(movimiento.fecha_entrada).strftime('%d/%m/%Y')
            p.drawString(50, y, fecha_entrada)
        else:
            fecha_ref = localtime(movimiento.fecha_salida).strftime('%d/%m/%Y') if movimiento.fecha_salida else "N/A"
            p.drawString(50, y, fecha_ref)
        
        # Hora entrada (máx 10 caracteres)
        if movimiento.fecha_entrada:
            hora_entrada = localtime(movimiento.fecha_entrada).strftime('%H:%M')
            p.drawString(110, y, hora_entrada)
        else:
            p.drawString(110, y, "---")
        
        # Hora salida (máx 10 caracteres)
        if movimiento.fecha_salida:
            hora_salida = localtime(movimiento.fecha_salida).strftime('%H:%M')
        else:
            hora_salida = "En Park." if movimiento.activo else "---"
        p.drawString(170, y, hora_salida)
        
        # Modalidad (truncado si es muy largo)
        modalidad = movimiento.get_modalidad_display() if hasattr(movimiento, 'get_modalidad_display') else movimiento.modalidad
        if len(modalidad) > 15:
            modalidad = modalidad[:12] + "..."
        p.drawString(240, y, modalidad)

        operario_nombre = movimiento.operario.username if movimiento.operario else "---"
        if len(operario_nombre) > 18:
            operario_nombre = operario_nombre[:18]
        p.drawString(340, y, operario_nombre)
        
        # Cobro
        cobro = movimiento.total_pagar if movimiento.total_pagar else 0
        p.drawString(460, y, f"${cobro:,.0f}")
        
        total_recaudado += cobro
        y -= 20  # Mayor espaciado entre filas
    
    # --- TOTAL GENERAL AL FINAL ---
    y -= 10  # Extra space antes del total
    p.line(50, y, 550, y)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(300, y - 20, "TOTAL COBRADO:")
    p.drawString(440, y - 20, f"${total_recaudado:,.0f} COP")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    
    nombre_archivo = f"historial_{placa_normalizada}.pdf"
    return HttpResponse(buffer, content_type='application/pdf', headers={'Content-Disposition': f'inline; filename="{nombre_archivo}"'})

@login_required
def control_mensualidad(request):
    ticket_mensualidad_id = request.session.pop('ticket_mensualidad_id', None)

    if request.method == 'POST':
        placa = normalizar_placa(request.POST.get('placa', ''))
        accion = request.POST.get('accion', '').strip().lower()
        # Nota: el HTML usa name="placa", asegúrate que coincida

        if not placa:
            messages.error(request, "Debes ingresar una placa válida.")
            return redirect('control_mensualidad')

        tipo_vehiculo = inferir_tipo_vehiculo(placa)
        if not tipo_vehiculo:
            messages.error(request, "Formato de placa no reconocido.")
            return redirect('control_mensualidad')

        # 1. BUSCAR CONTRATO VIGENTE
        contrato_vigente = (
            Reserva.objects.filter(
                placa=placa,
                modalidad='MENSUALIDAD',
                es_pago_mensualidad=True, # Buscamos el último recibo de pago
                fecha_vencimiento__gte=timezone.now(),
            )
            .order_by('-fecha_vencimiento')
            .first()
        )

        if accion == 'entrada':
            # Verificar si ya está adentro
            reserva_activa = Reserva.objects.filter(placa=placa, activo=True).first()
            if reserva_activa:
                messages.warning(request, f"El vehículo {placa} ya se encuentra adentro.")
                return redirect('control_mensualidad')

            # LÓGICA DE COBRO O MOVIMIENTO SIMPLE
            if contrato_vigente:
                # Caso A: Tiene contrato, solo registramos el movimiento (es_pago_mensualidad=False)
                Reserva.objects.create(
                    placa=placa,
                    tipo_vehiculo=tipo_vehiculo,
                    modalidad='MENSUALIDAD',
                    fecha_entrada=timezone.now(),
                    es_pago_mensualidad=False, # MOVIMIENTO DIARIO
                    activo=True,
                    total_pagar=Decimal('0.00'),
                    fecha_vencimiento=contrato_vigente.fecha_vencimiento,
                    usuario_registro=request.user,
                    operario=request.user,
                )
                messages.success(request, f"✅ ENTRADA: {placa} ingresó con plan vigente.")
            else:
                # Caso B: No tiene contrato o venció, REGISTRAMOS PAGO (es_pago_mensualidad=True)
                cobro = Decimal(str(MENSUALIDAD_CARRO if tipo_vehiculo == 'CARRO' else MENSUALIDAD_MOTO))
                vence = timezone.now() + timedelta(days=30)
                
                nuevo_pago = Reserva.objects.create(
                    placa=placa,
                    tipo_vehiculo=tipo_vehiculo,
                    modalidad='MENSUALIDAD',
                    fecha_entrada=timezone.now(),
                    es_pago_mensualidad=True, # ESTO ES UN PAGO NUEVO
                    activo=True,
                    total_pagar=cobro,
                    fecha_vencimiento=vence,
                    usuario_registro=request.user,
                    operario=request.user,
                )
                request.session['ticket_mensualidad_id'] = nuevo_pago.id
                messages.success(request, f"💰 PAGO REGISTRADO: {placa} pagó mes y entró. Vence: {vence.strftime('%d/%m/%Y')}")

        elif accion == 'salida':
            reserva_activa = Reserva.objects.filter(placa=placa, activo=True).order_by('-id').first()
            if reserva_activa:
                fecha_salida_ahora = timezone.now()
                
                # Verificar si el usuario que saca es diferente al que ingresó
                usuario_diferente = reserva_activa.usuario_registro != request.user
                
                if usuario_diferente:
                    # Crear registro de SOLO SALIDA
                    Reserva.objects.create(
                        placa=reserva_activa.placa,
                        tipo_vehiculo=reserva_activa.tipo_vehiculo,
                        modalidad='MENSUALIDAD',
                        fecha_entrada=None,  # Registro de solo salida
                        fecha_salida=fecha_salida_ahora,
                        registra_solo_salida=True,
                        total_pagar=Decimal('0.00'),
                        usuario_registro=None,
                        operario=request.user,
                        es_pago_mensualidad=False,
                        activo=False,
                        fecha_vencimiento=reserva_activa.fecha_vencimiento,
                    )
                    # El registro original NO recibe fecha_salida
                    reserva_activa.activo = False
                    # NO asignamos fecha_salida al registro original
                else:
                    # Mismo usuario: salida completa
                    reserva_activa.fecha_salida = fecha_salida_ahora
                    reserva_activa.activo = False
                    reserva_activa.operario = request.user
                
                reserva_activa.save()
                messages.success(request, f"✅ SALIDA: {placa} salió correctamente.")
            else:
                messages.warning(request, f"La placa {placa} no registra una entrada activa.")

        return redirect('control_mensualidad')

    # --- LÓGICA DEL GET (Listado) ---
    placa_filtro = request.GET.get('placa_buscar', '').strip().upper()
    movimientos_qs = (
        Reserva.objects.filter(modalidad='MENSUALIDAD')
        .annotate(
            fecha_efectiva=Coalesce('fecha_entrada', 'fecha_salida')
        )
        .select_related('operario', 'usuario_registro')
        .order_by('-fecha_efectiva')
    )
    if placa_filtro:
        movimientos_qs = movimientos_qs.filter(placa__icontains=placa_filtro)

    paginator = Paginator(movimientos_qs, 5)
    page_number = request.GET.get('page')
    ultimos_movimientos = paginator.get_page(page_number)

    return render(request, 'reservas/control_mensualidad.html', {
        'ultimos_movimientos': ultimos_movimientos,
        'placa_filtro': placa_filtro,
        'total_resultados': movimientos_qs.count(),
        'ticket_mensualidad_id': ticket_mensualidad_id,
    })
