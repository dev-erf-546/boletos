import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!

SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = True

ALLOWED_HOSTS = [
    "boletos.pulsarmex.com",
    "www.boletos.pulsarmex.com",
    "pulsarmex.com",
    "localhost",

]
DEBUG = os.getenv('DEBUG') == 'True'
#ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS').split(',')

SITE_URL = os.getenv('SITE_URL', 'https://boletos.pulsarmex.com')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites', 
    'rest_framework',
    'eventos',

    # Apps de allaut
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
]

SITE_ID = 1 

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware', 
]

ROOT_URLCONF = 'boletos.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'boletos.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
     'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
        # 'NAME': 'boletos',
        # 'USER': 'postgres',
        # 'PASSWORD': '12345678',
        # 'HOST': 'localhost',
        # 'PORT': 5432,
    }
}

# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Mexico_City'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = '/home/webapps/rifa/static' 
# Modificado: 2026-03-17 22:10:50 - Agregar carpeta static del proyecto a STATICFILES_DIRS
# Solo agregar static_extra si el directorio existe
static_extra_dir = os.path.join(BASE_DIR, 'static_extra')
static_dirs = [static_extra_dir] if os.path.exists(static_extra_dir) else []
# Agregar la carpeta static del proyecto si existe
static_project_dir = os.path.join(BASE_DIR, 'static')
if os.path.exists(static_project_dir):
    static_dirs.append(static_project_dir)
STATICFILES_DIRS = static_dirs
MEDIA_URL = '/storage/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'storage')

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configuración de sesión
SESSION_COOKIE_AGE = 86400  # 1 día en segundos
SESSION_SAVE_EVERY_REQUEST = True

# Configuración de archivos permitidos
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB - Archivos en memoria
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB - Datos del formulario
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240  # Número máximo de campos en formulario
FILE_UPLOAD_TEMP_DIR = None  # Usar directorio temporal del sistema para archivos grandes

# Configuración de autenticación
AUTHENTICATION_BACKENDS = [
    # Necesario para iniciar sesión por username en el admin
    'django.contrib.auth.backends.ModelBackend',
    
    # Método de autenticación específico de allauth
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Configuración de allauth (versión actualizada - sin deprecaciones)
# Métodos de login permitidos: username, email, o ambos
ACCOUNT_LOGIN_METHODS = {'username', 'email'}  # Permite login con usuario o email

# Campos en el formulario de registro (los campos con * son requeridos)
# Formato: ['campo1', 'campo2*', 'campo3*'] donde * indica requerido
ACCOUNT_SIGNUP_FIELDS = ['email', 'username*', 'password1*', 'password2*']

# Verificación de email
ACCOUNT_EMAIL_VERIFICATION = 'none'  # 'mandatory' o 'optional'

# Cerrar sesión con GET
ACCOUNT_LOGOUT_ON_GET = True  # Cierra sesión con solo visitar /accounts/logout/

# Modificado: 2026-03-17 22:10:50 - Configuración de redirect al admin-panel después del login
# URLs de redirección - Solo se usa el admin de Django, no allauth
LOGIN_REDIRECT_URL = '/admin-panel/'  # Redirigir al panel admin después del login
LOGOUT_REDIRECT_URL = '/'  # Redirigir al inicio después del logout

# Adaptador personalizado de allauth deshabilitado (ya no se usa allauth)
# ACCOUNT_ADAPTER = 'eventos.adapters.CustomAccountAdapter'

# Configuración de seguridad para producción
if not DEBUG:
    # CSRF
    CSRF_COOKIE_SECURE = True  # Solo enviar cookies CSRF sobre HTTPS
    CSRF_COOKIE_HTTPONLY = True
    CSRF_TRUSTED_ORIGINS = [
        'https://boletos.pulsarmex.com',
        'https://www.boletos.pulsarmex.com',
        'https://pulsarmex.com',
        'http://localhost',
    ]
    
    # Cookies de sesión
    SESSION_COOKIE_SECURE = True  # Solo enviar cookies de sesión sobre HTTPS
    SESSION_COOKIE_HTTPONLY = True
    
    # Seguridad adicional
    SECURE_SSL_REDIRECT = False  # Desactivar si usas un proxy reverso (nginx/apache)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# settings.py (versión segura para producción)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-mail.outlook.com'  # Servidor SMTP de Outlook/Hotmail
EMAIL_PORT = 587  # Puerto para TLS (seguro)
EMAIL_USE_TLS = True  # Obligatorio para Hotmail/Outlook
EMAIL_HOST_USER = 'pulsarmex@hotmail.com'  # Tu email completo
EMAIL_HOST_PASSWORD = 'Pulsarm3xTab'  # La misma que usas para iniciar sesión en Hotmail
DEFAULT_FROM_EMAIL = 'pulsarmex@hotmail.com'  # Email remitente