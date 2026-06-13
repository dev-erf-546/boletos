"""
Generador de PDF para talonarios/boletos físicos de rifa (ReportLab).

Ajuste rápido de layout: modifique TalonarioConfig.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable, List, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas


@dataclass
class TalonarioConfig:
    """Parámetros físicos del talonario. Todas las medidas en centímetros."""

    # Tamaño de cada boleto
    ancho_cm: float = 8.2
    alto_cm: float = 6.9

    # Hoja carta (letter)
    page_size: Tuple[float, float] = letter

    # Márgenes de la hoja
    margen_izquierdo_cm: float = 1.0
    margen_superior_cm: float = 1.0
    margen_derecho_cm: float = 1.0
    margen_inferior_cm: float = 1.0

    # Cuadrícula
    columnas: int = 2
    separacion_horizontal_cm: float = 0.4
    separacion_vertical_cm: float = 0.4

    # Textos fijos del diseño
    titulo_rifa: str = 'RIFA 3ra. GRAN CABALGATA'
    subtitulo: str = 'Sagrado Corazón De Jesús'

    # Tipografías (puntos)
    font_titulo: int = 7
    font_subtitulo: int = 6
    font_campo: int = 6
    font_valor: int = 6
    font_valor_monto: int = 7
    font_numero: int = 11

    @property
    def ancho_boleto(self) -> float:
        return self.ancho_cm * cm

    @property
    def alto_boleto(self) -> float:
        return self.alto_cm * cm

    @property
    def gap_h(self) -> float:
        return self.separacion_horizontal_cm * cm

    @property
    def gap_v(self) -> float:
        return self.separacion_vertical_cm * cm


def _truncar(texto: str | None, max_len: int) -> str:
    if not texto:
        return ''
    s = str(texto).strip()
    return s if len(s) <= max_len else s[: max_len - 1] + '…'


def _filas_por_pagina(config: TalonarioConfig) -> int:
    _, page_h = config.page_size
    margen_v = (config.margen_superior_cm + config.margen_inferior_cm) * cm
    usable_h = page_h - margen_v
    slot = config.alto_boleto + config.gap_v
    if slot <= 0:
        return 1
    return max(1, int((usable_h + config.gap_v) // slot))


def _boletos_por_pagina(config: TalonarioConfig) -> int:
    return config.columnas * _filas_por_pagina(config)


def _posicion_boleto(indice_en_pagina: int, config: TalonarioConfig) -> Tuple[float, float]:
    """Devuelve (x_inferior_izquierda, y_inferior) en coordenadas ReportLab."""
    page_w, page_h = config.page_size
    col = indice_en_pagina % config.columnas
    fila = indice_en_pagina // config.columnas

    x = config.margen_izquierdo_cm * cm + col * (config.ancho_boleto + config.gap_h)
    y_top = page_h - (config.margen_superior_cm * cm) - fila * (
        config.alto_boleto + config.gap_v
    )
    y = y_top - config.alto_boleto
    return x, y


def dibujar_talonario_fisico(pdf: canvas.Canvas, boleto, x: float, y: float, config: TalonarioConfig) -> None:
    """Dibuja un talonario en (x, y) = esquina inferior izquierda."""
    w = config.ancho_boleto
    h = config.alto_boleto
    pad = 2 * mm
    label_w = 18 * mm

    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.6)
    pdf.rect(x, y, w, h, stroke=1, fill=0)

    participante = boleto.participante
    nombre = _truncar(getattr(participante, 'nombre_completo', None), 34)
    domicilio = _truncar(getattr(participante, 'direccion', None) or '-', 34)
    telefono = _truncar(getattr(participante, 'telefono', None) or '-', 20)
    precio = boleto.rifa.precio_boleto

    y_cursor = y + h - pad

    pdf.setFillColor(colors.black)
    pdf.setFont('Helvetica-Bold', config.font_titulo)
    pdf.drawCentredString(x + w / 2, y_cursor - 2.5 * mm, config.titulo_rifa)
    y_cursor -= 4.5 * mm

    pdf.setFont('Helvetica', config.font_subtitulo)
    pdf.drawCentredString(x + w / 2, y_cursor - 2.5 * mm, config.subtitulo)
    y_cursor -= 4 * mm

    pdf.setLineWidth(0.4)
    pdf.line(x + pad, y_cursor - 1 * mm, x + w - pad, y_cursor - 1 * mm)
    y_cursor -= 5 * mm

    campos = (
        ('NOMBRE:', nombre),
        ('DOMICILIO:', domicilio),
        ('TELEFONO:', telefono),
    )
    for etiqueta, valor in campos:
        pdf.setFont('Helvetica-Bold', config.font_campo)
        pdf.drawString(x + pad, y_cursor - 2 * mm, etiqueta)

        val_x = x + pad + label_w
        val_right = x + w - pad
        pdf.setFont('Helvetica', config.font_valor)
        pdf.drawString(val_x, y_cursor - 2 * mm, valor)
        pdf.line(val_x, y_cursor - 3.2 * mm, val_right, y_cursor - 3.2 * mm)
        y_cursor -= 7.5 * mm

    bottom_y = y + pad + 1.5 * mm
    pdf.setFont('Helvetica-Bold', config.font_valor_monto)
    pdf.drawString(x + pad, bottom_y, f'VALOR $ {precio:.2f}')

    pdf.setFillColor(colors.red)
    pdf.setFont('Helvetica-Bold', config.font_numero)
    pdf.drawRightString(x + w - pad, bottom_y, f'N° {boleto.numero}')
    pdf.setFillColor(colors.black)


def generar_pdf_talonarios(boletos: Sequence, config: TalonarioConfig | None = None) -> bytes:
    """Genera bytes PDF con los talonarios dados, ordenados por número."""
    if not boletos:
        raise ValueError('No hay boletos para imprimir.')

    config = config or TalonarioConfig()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=config.page_size)

    por_pagina = _boletos_por_pagina(config)
    for i, boleto in enumerate(boletos):
        idx_pagina = i % por_pagina
        if i > 0 and idx_pagina == 0:
            pdf.showPage()

        x, y = _posicion_boleto(idx_pagina, config)
        dibujar_talonario_fisico(pdf, boleto, x, y, config)

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
