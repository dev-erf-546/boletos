import os
from io import BytesIO
from django.core.files import File
import qrcode
from django.conf import settings

def generar_qr_imagen(qr_instance):
    try:
        # 1. Crear directorio si no existe
        qr_dir = os.path.join(settings.MEDIA_ROOT, 'qrs')
        os.makedirs(qr_dir, exist_ok=True)
        
        # 2. Generar contenido QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f"Boleto:{qr_instance.boleto.id}-Codigo:{qr_instance.codigo}")
        qr.make(fit=True)
        
        # 3. Crear imagen
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 4. Guardar en buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # 5. Nombre de archivo único
        nombre_archivo = f"qr_{qr_instance.boleto.id}_{qr_instance.codigo[:8]}.png"
        
        # 6. Eliminar imagen anterior si existe
        if qr_instance.imagen_qr:
            if os.path.exists(qr_instance.imagen_qr.path):
                os.remove(qr_instance.imagen_qr.path)
        
        # 7. Guardar nueva imagen
        qr_instance.imagen_qr.save(nombre_archivo, File(buffer))
        buffer.close()
        
        # 8. Forzar guardado del modelo
        qr_instance.save()
        
        return True
    except Exception as e:
        print(f"Error generando QR: {str(e)}")
        return False