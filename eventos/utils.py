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
    from io import BytesIO
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    import uuid
    import os

    print("=== Generando QR para boleto ===")
    buffer = None
    try:
        boleto = qr_instance.boleto
        participante = boleto.participante

        # 1. Preparar contenido del QR
        qr_content = f"""ERMITA SAGRADO CORAZÓN DE JESÚS
        Boleto: {boleto.numero}
        Rifa: {boleto.rifa.nombre}
        Participante: {participante.nombre_completo if participante else 'N/A'}
        Teléfono: {participante.telefono if participante else 'N/A'}
        """

        # 2. Generar imagen QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5,
            border=4,
        )
        qr.add_data(qr_content)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        
        # 3. Crear imagen combinada con texto
        img = Image.new('RGB', (700, 300), color='white')
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except Exception as fe:
            print(f"⚠️ Fuente no encontrada: {fe}")
            font = ImageFont.load_default()

        draw.text((50, 50), f"BOLETO #{boleto.numero}", font=font, fill="black")
        draw.text((50, 100), f"Rifa: {boleto.rifa.nombre}", font=font, fill="black")
        if participante:
            draw.text((50, 150), f"Participante: {participante.nombre_completo}", font=font, fill="black")
            draw.text((50, 200), f"Teléfono: {participante.telefono}", font=font, fill="black")
        img.paste(qr_img, (400, 20))

        # 4. Guardar en buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        # 5. Eliminar QR anterior
        if qr_instance.imagen_qr:
            try:
                old_path = qr_instance.imagen_qr.path
                if os.path.exists(old_path):
                    os.remove(old_path)
                    
            except Exception as e:
                print(f"⚠️ Error eliminando imagen anterior: {e}")

        # 6. Guardar nueva imagen
        file_name = f"qr_boleto_{boleto.numero}_{uuid.uuid4().hex[:6]}.png"
        qr_instance.imagen_qr.save(file_name, File(buffer))


        # 7. Forzar guardado
        qr_instance.save()

        buffer.close()
        return True

    except Exception as e:
        print(f"❌ Error general: {str(e)}")
        import traceback
        traceback.print_exc()
        if buffer:
            try:
                buffer.close()
            except:
                pass
        return False
