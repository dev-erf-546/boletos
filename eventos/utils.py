from django.core.files import File
from io import BytesIO
import qrcode
import os
import uuid
import logging
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

from .models import QRBoleto

logger = logging.getLogger(__name__)

MESES_ES = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
    7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
}

FONT_PATHS_BOLD = [
    'C:/Windows/Fonts/arialbd.ttf',
    'C:/Windows/Fonts/calibrib.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
]

FONT_PATHS_REGULAR = [
    'C:/Windows/Fonts/arial.ttf',
    'C:/Windows/Fonts/calibri.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
]

ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')


def _load_font(paths, size):
    for p in paths:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.truetype('arial.ttf', size)
    except Exception:
        return ImageFont.load_default()


def _center_text(draw, text, font, y, canvas_width, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (canvas_width - text_w) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def _overlay_logo_on_qr(qr_img):
    """
    Superpone el logo institucional en el centro del QR.
    Usa nivel H de corrección de errores (~30% del QR puede estar cubierto).
    El logo ocupa ~22% del área del QR para mantener margen de escaneo seguro.
    """
    logo_path = os.path.join(ASSETS_DIR, 'logo_qr.png')
    if not os.path.exists(logo_path):
        logger.warning("Logo no encontrado en %s, QR sin logo", logo_path)
        return qr_img

    try:
        logo = Image.open(logo_path).convert('RGBA')
        qr_w, qr_h = qr_img.size

        # El logo ocupa ~22% del ancho del QR (seguro con ERROR_CORRECT_H)
        logo_max = int(qr_w * 0.22)
        logo.thumbnail((logo_max, logo_max), Image.Resampling.LANCZOS)
        logo_w, logo_h = logo.size

        # Padding alrededor del logo para el fondo blanco
        padding = int(logo_w * 0.18)
        bg_w = logo_w + padding * 2
        bg_h = logo_h + padding * 2

        # Fondo blanco con bordes redondeados detrás del logo
        bg = Image.new('RGBA', (bg_w, bg_h), (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bg)
        radius = int(bg_w * 0.15)
        bg_draw.rounded_rectangle(
            [(0, 0), (bg_w - 1, bg_h - 1)],
            radius=radius,
            fill=(255, 255, 255, 255),
        )

        # Pegar el logo centrado sobre el fondo blanco
        logo_offset_x = (bg_w - logo_w) // 2
        logo_offset_y = (bg_h - logo_h) // 2
        bg.paste(logo, (logo_offset_x, logo_offset_y), logo)

        # Pegar el bloque (fondo + logo) en el centro del QR
        pos_x = (qr_w - bg_w) // 2
        pos_y = (qr_h - bg_h) // 2
        qr_img.paste(bg, (pos_x, pos_y), bg)

        return qr_img

    except Exception as e:
        logger.error("Error superponiendo logo en QR: %s", e, exc_info=True)
        return qr_img


def generar_qr_boleto(qr_instance):
    """
    Genera el boleto digital usando el patrón de fondo profesional.
    El QR contiene la URL de verificación con el UUID del boleto.
    """
    buffer = None
    try:
        boleto = qr_instance.boleto
        participante = boleto.participante
        rifa = boleto.rifa

        # --- Cargar patrón de fondo ---
        patron_path = os.path.join(ASSETS_DIR, 'boleto_patron.png')
        img = Image.open(patron_path).convert('RGBA')
        w, h = img.size

        txt_layer = Image.new('RGBA', (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        # --- Fuentes (proporcionales al canvas de 745x1024) ---
        scale = w / 745.0
        font_boleto_num = _load_font(FONT_PATHS_BOLD, int(40 * scale))
        font_label = _load_font(FONT_PATHS_BOLD, int(22 * scale))
        font_value = _load_font(FONT_PATHS_REGULAR, int(22 * scale))

        color_text = '#3d0e00'

        # --- BOLETO #X (centrado entre las líneas horizontales del patrón) ---
        boleto_text = f"BOLETO #{boleto.numero}"
        boleto_y = int(h * 0.335)
        _center_text(draw, boleto_text, font_boleto_num, boleto_y, w, color_text)

        # --- Info del participante (debajo de la segunda línea) ---
        left_pad = int(w * 0.12)
        info_y = int(h * 0.415)
        line_h = int(28 * scale)

        if participante:
            label = "Participante:  "
            value = participante.nombre_completo
            lbox = draw.textbbox((0, 0), label, font=font_label)
            draw.text((left_pad, info_y), label, font=font_label, fill=color_text)
            draw.text((left_pad + lbox[2] - lbox[0], info_y), value, font=font_value, fill=color_text)

            info_y += line_h + int(12 * scale)

            tel_label = "Teléfono:  "
            tel_value = participante.telefono
            tbox = draw.textbbox((0, 0), tel_label, font=font_label)
            draw.text((left_pad, info_y), tel_label, font=font_label, fill=color_text)
            tel_end_x = left_pad + tbox[2] - tbox[0]
            draw.text((tel_end_x, info_y), tel_value, font=font_value, fill=color_text)

            vbox = draw.textbbox((0, 0), tel_value, font=font_value)
            fecha_x = tel_end_x + vbox[2] - vbox[0] + int(30 * scale)
        else:
            fecha_x = left_pad

        fecha_sorteo = rifa.fecha_sorteo
        fecha_text = f"{fecha_sorteo.day} de {MESES_ES.get(fecha_sorteo.month, '')} de {fecha_sorteo.year}"
        draw.text((fecha_x, info_y), fecha_text, font=font_value, fill=color_text)

        # --- Generar QR con URL de verificación ---
        base_url = getattr(settings, 'SITE_URL', 'https://boletos.pulsarmex.com')
        qr_url = f"{base_url}/boleto/{qr_instance.codigo}/"

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=3,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')

        qr_size = int(w * 0.375)
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # --- Superponer logo en el centro del QR (estilo WhatsApp) ---
        qr_img = _overlay_logo_on_qr(qr_img)

        qr_x = (w - qr_size) // 2
        qr_y = int(h * 0.545)

        # --- Componer capas ---
        img = Image.alpha_composite(img, txt_layer)
        img.paste(qr_img, (qr_x, qr_y), qr_img)
        final = img.convert('RGB')

        # --- Guardar ---
        buffer = BytesIO()
        final.save(buffer, format='PNG', quality=95, optimize=True)
        buffer.seek(0)

        if qr_instance.imagen_qr:
            try:
                old_path = qr_instance.imagen_qr.path
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception:
                pass

        file_name = f"boleto_{boleto.numero}_{uuid.uuid4().hex[:6]}.png"
        qr_instance.imagen_qr.save(file_name, File(buffer))
        qr_instance.save()
        buffer.close()

        logger.info("Boleto generado: %s", file_name)
        return True

    except Exception as e:
        logger.error("Error generando boleto: %s", e, exc_info=True)
        if buffer:
            try:
                buffer.close()
            except Exception:
                pass
        return False
