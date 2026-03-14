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

def generar_qr_boleto(qr_instance):
    """
    Genera una imagen completa del boleto con diseño moderno tipo tarjeta.
    Incluye información del boleto y código QR.
    """
    from io import BytesIO
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    import uuid
    import os
    from datetime import datetime

    print("=== Generando boleto digital con diseño moderno ===")
    buffer = None
    try:
        boleto = qr_instance.boleto
        participante = boleto.participante
        rifa = boleto.rifa

        # 1. Preparar contenido del QR
        qr_content = f"""ERMITA SAGRADO CORAZÓN DE JESÚS
            Boleto: {boleto.numero}
            Rifa: {rifa.nombre}
            Participante: {participante.nombre_completo if participante else 'N/A'}
            Teléfono: {participante.telefono if participante else 'N/A'}
            Fecha Sorteo: {rifa.fecha_sorteo.strftime('%d/%m/%Y')}
        """

        # 2. Generar código QR (mejorado para mejor escaneo)
        qr = qrcode.QRCode(
            version=None,  # Auto-ajustar versión según contenido
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Mayor corrección de errores
            box_size=10,  # Aumentado para mejor resolución
            border=4,  # Borde más grande para mejor detección
        )
        qr.add_data(qr_content)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        
        # Redimensionar QR a tamaño adecuado (más grande para mejor escaneo)
        qr_size = 250  # Aumentado de 200 a 250
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # 3. Crear imagen del boleto completo (formato impresora de tickets - más estrecho)
        img_width = 500  # Reducido de 700 a 500 (formato ticket)
        img_height = 600  # Aumentado para acomodar contenido vertical
        img = Image.new('RGB', (img_width, img_height), color='#ffffff')
        draw = ImageDraw.Draw(img)

        # Intentar cargar fuentes
        try:
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                'arial.ttf',
            ]
            title_font = None
            subtitle_font = None
            boleto_font = None
            label_font = None
            value_font = None
            
            for path in font_paths:
                try:
                    if os.path.exists(path):
                        title_font = ImageFont.truetype(path, 24)  #32 Para "RIFA 3ra GRAN CABALGATA"
                        subtitle_font = ImageFont.truetype(path, 18)  #20 Para "Sagrado Corazón de Jesús"
                        boleto_font = ImageFont.truetype(path, 30)  #36 Para "BOLETO #402"
                        label_font = ImageFont.truetype(path, 14)  #16 Para labels
                        value_font = ImageFont.truetype(path, 14)  #16 Para valores
                        break
                except:
                    continue
            
            if not title_font:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
                boleto_font = ImageFont.load_default()
                label_font = ImageFont.load_default()
                value_font = ImageFont.load_default()
        except Exception as fe:
            print(f"⚠️ Usando fuente por defecto: {fe}")
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            boleto_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
            value_font = ImageFont.load_default()

        # Colores (negro sobre blanco como en la imagen)
        color_text_primary = '#000000'
        color_border = '#000000'

        # === BORDES: Sólido arriba, punteado en lados y abajo ===
        # Borde superior sólido (más grueso)
        draw.line([(0, 0), (img_width, 0)], fill=color_border, width=3)
        
        # Bordes laterales punteados
        dash_length = 8
        gap_length = 4
        for y in range(0, img_height, dash_length + gap_length):
            # Lado izquierdo
            end_y = min(y + dash_length, img_height)
            draw.line([(0, y), (0, end_y)], fill=color_border, width=2)
            # Lado derecho
            draw.line([(img_width-1, y), (img_width-1, end_y)], fill=color_border, width=2)
        
        # Borde inferior punteado
        for x in range(0, img_width, dash_length + gap_length):
            end_x = min(x + dash_length, img_width)
            draw.line([(x, img_height-1), (end_x, img_height-1)], fill=color_border, width=2)

        # === CONTENIDO DEL BOLETO ===
        left_padding = 20  # Reducido de 40 a 20 (menos espacio lateral)
        top_padding = 25
        current_y = top_padding
        line_spacing = 6

        # 1. Título de la Rifa (centrado, mayúsculas)
        rifa_title = rifa.nombre.upper()
        title_bbox = draw.textbbox((0, 0), rifa_title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (img_width - title_width) // 2
        draw.text((title_x, current_y), rifa_title, font=title_font, fill=color_text_primary)
        current_y += title_bbox[3] - title_bbox[1] + line_spacing

        # 2. Subtítulo (centrado) - "Sagrado Corazón de Jesús"
        subtitle_text = "Sagrado Corazón de Jesús"
        subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        subtitle_x = (img_width - subtitle_width) // 2
        draw.text((subtitle_x, current_y), subtitle_text, font=subtitle_font, fill=color_text_primary)
        current_y += subtitle_bbox[3] - subtitle_bbox[1] + 20

        # Línea separadora horizontal (de borde a borde)
        draw.line([(left_padding, current_y), (img_width - left_padding, current_y)], fill=color_border, width=1)
        current_y += 15

        # 3. Número de Boleto (centrado, destacado)
        boleto_text = f"BOLETO #{boleto.numero}"
        boleto_bbox = draw.textbbox((0, 0), boleto_text, font=boleto_font)
        boleto_width = boleto_bbox[2] - boleto_bbox[0]
        boleto_x = (img_width - boleto_width) // 2
        draw.text((boleto_x, current_y), boleto_text, font=boleto_font, fill=color_text_primary)
        current_y += boleto_bbox[3] - boleto_bbox[1] + 20

        # Línea separadora horizontal (de borde a borde)
        draw.line([(left_padding, current_y), (img_width - left_padding, current_y)], fill=color_border, width=1)
        current_y += 15

        # 4. Información del participante (alineado a la izquierda, label: valor en misma línea)
        if participante:
            # Participante: [nombre]
            participante_label = "Participante:"
            participante_value = participante.nombre_completo
            label_bbox = draw.textbbox((0, 0), participante_label, font=label_font)
            draw.text((left_padding, current_y), participante_label, font=label_font, fill=color_text_primary)
            draw.text((left_padding + label_bbox[2] - label_bbox[0] + 8, current_y), participante_value, font=value_font, fill=color_text_primary)
            value_bbox = draw.textbbox((0, 0), participante_value, font=value_font)
            current_y += max(label_bbox[3] - label_bbox[1], value_bbox[3] - value_bbox[1]) + 12

            # Teléfono: [número]
            telefono_label = "Teléfono:"
            telefono_value = participante.telefono
            label_bbox = draw.textbbox((0, 0), telefono_label, font=label_font)
            draw.text((left_padding, current_y), telefono_label, font=label_font, fill=color_text_primary)
            draw.text((left_padding + label_bbox[2] - label_bbox[0] + 8, current_y), telefono_value, font=value_font, fill=color_text_primary)
            value_bbox = draw.textbbox((0, 0), telefono_value, font=value_font)
            current_y += max(label_bbox[3] - label_bbox[1], value_bbox[3] - value_bbox[1]) + 12

        # Fecha del sorteo: [fecha]
        meses = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
            7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }
        fecha_sorteo = rifa.fecha_sorteo
        fecha_text = f"{fecha_sorteo.day} de {meses.get(fecha_sorteo.month, 'mes')} de {fecha_sorteo.year}"
        fecha_label = "Fecha del sorteo:"
        label_bbox = draw.textbbox((0, 0), fecha_label, font=label_font)
        draw.text((left_padding, current_y), fecha_label, font=label_font, fill=color_text_primary)
        draw.text((left_padding + label_bbox[2] - label_bbox[0] + 8, current_y), fecha_text, font=value_font, fill=color_text_primary)
        value_bbox = draw.textbbox((0, 0), fecha_text, font=value_font)
        current_y += max(label_bbox[3] - label_bbox[1], value_bbox[3] - value_bbox[1]) + 20

        # Línea separadora antes del QR
        draw.line([(left_padding, current_y), (img_width - left_padding, current_y)], fill=color_border, width=1)
        current_y += 20

        # === SECCIÓN QR (centrado en la parte inferior, más grande) ===
        qr_size_final = 220  # Aumentado de 180 a 220 para mejor escaneo
        qr_img_resized = qr_img.resize((qr_size_final, qr_size_final), Image.Resampling.LANCZOS)
        
        # Centrar QR horizontalmente
        qr_x = (img_width - qr_size_final) // 2
        qr_y = current_y
        
        # Pegar QR
        img.paste(qr_img_resized, (qr_x, qr_y))

        # === FOOTER (opcional, más abajo si hay espacio) ===
        footer_y = img_height - 25
        footer_text = "https://pulsarmex.com/"
        footer_bbox = draw.textbbox((0, 0), footer_text, font=label_font)
        footer_text_width = footer_bbox[2] - footer_bbox[0]
        footer_x = (img_width - footer_text_width) // 2
        draw.text((footer_x, footer_y), footer_text, font=label_font, fill=color_text_primary)

        # 4. Guardar en buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG', quality=95, optimize=True)
        buffer.seek(0)

        # 5. Eliminar imagen anterior si existe
        if qr_instance.imagen_qr:
            try:
                old_path = qr_instance.imagen_qr.path
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception as e:
                print(f"⚠️ Error eliminando imagen anterior: {e}")

        # 6. Guardar nueva imagen
        file_name = f"boleto_{boleto.numero}_{uuid.uuid4().hex[:6]}.png"
        qr_instance.imagen_qr.save(file_name, File(buffer))

        # 7. Forzar guardado
        qr_instance.save()

        buffer.close()
        print(f"✅ Boleto generado exitosamente: {file_name}")
        return True

    except Exception as e:
        print(f"❌ Error general generando boleto: {str(e)}")
        import traceback
        traceback.print_exc()
        if buffer:
            try:
                buffer.close()
            except:
                pass
        return False
