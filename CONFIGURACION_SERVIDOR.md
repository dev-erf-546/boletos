# Configuración del Servidor Web para Solucionar Error 413

## Error 413 Request Entity Too Large

Este error ocurre cuando el tamaño de la solicitud HTTP excede los límites configurados.

## Configuración para Nginx

Si estás usando **Nginx** como servidor web, agrega o modifica estas líneas en tu configuración:

```nginx
# En el bloque http o server
client_max_body_size 20M;  # Permite archivos hasta 20MB
client_body_buffer_size 128k;
client_body_timeout 60s;
```

**Ubicación del archivo de configuración:**
- `/etc/nginx/nginx.conf` (configuración global)
- `/etc/nginx/sites-available/tu-sitio` (configuración del sitio específico)

**Ejemplo completo para un sitio:**

```nginx
server {
    listen 80;
    server_name boletos.pulsarmex.com;
    
    # Límite de tamaño de cuerpo de solicitud
    client_max_body_size 20M;
    
    location / {
        proxy_pass http://127.0.0.1:8000;  # O el puerto de tu aplicación Django
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /storage/ {
        alias /ruta/a/tu/proyecto/storage/;
    }
    
    location /static/ {
        alias /home/webapps/rifa/static/;
    }
}
```

**Después de modificar nginx, reinicia el servicio:**

```bash
sudo nginx -t  # Verificar configuración
sudo systemctl reload nginx  # O restart nginx
```

## Configuración para Apache

Si estás usando **Apache**, agrega estas directivas:

```apache
# En el archivo de configuración del sitio o .htaccess
LimitRequestBody 20971520  # 20MB en bytes
```

**Ubicación:**
- Archivo de configuración del sitio virtual
- O en `.htaccess` en el directorio del proyecto

**Ejemplo:**

```apache
<VirtualHost *:80>
    ServerName boletos.pulsarmex.com
    
    LimitRequestBody 20971520  # 20MB
    
    # ... resto de configuración
</VirtualHost>
```

**Reiniciar Apache:**

```bash
sudo apache2ctl configtest  # Verificar configuración
sudo systemctl restart apache2  # O httpd
```

## Verificar la Configuración

1. **Reinicia tu aplicación Django/Gunicorn:**
   ```bash
   sudo systemctl restart gunicorn
   # O el método que uses
   ```

2. **Verifica los logs:**
   ```bash
   # Logs de Nginx
   sudo tail -f /var/log/nginx/error.log
   
   # Logs de Django/Gunicorn
   sudo tail -f /var/log/gunicorn/error.log
   ```

## Límites Configurados en Django

- **Tamaño máximo de archivo:** 10MB
- **Tamaño máximo de datos del formulario:** 10MB
- **Número máximo de campos:** 10,240

## Validaciones Agregadas

El formulario ahora valida:
- Tamaño máximo de imagen: 10MB
- Tipos de archivo permitidos: JPEG, PNG, GIF, WebP
- Longitud máxima de descripción: 5,000 caracteres
- Longitud máxima de premio principal: 2,000 caracteres
- Máximo de boletos: 99,999
