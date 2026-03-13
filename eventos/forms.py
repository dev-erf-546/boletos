from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Participante, ComprobantePago, Rifa

class RegistroParticipanteForm(forms.ModelForm):
    class Meta:
        model = Participante
        fields = ['nombre_completo', 'telefono', 'email', 'metodo_contacto']
        widgets = {
            'metodo_contacto': forms.RadioSelect()
        }

class SubirComprobanteForm(forms.ModelForm):
    class Meta:
        model = ComprobantePago
        fields = ['imagen']
        labels = {
            'imagen': 'Comprobante de pago (imagen o PDF)'
        }

class ValidarComprobanteForm(forms.ModelForm):
    ESTADO_CHOICES = [
        ('A', 'Aprobado'),
        ('R', 'Rechazado'),
        ('P', 'Pendiente'),
    ]
    
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        widget=forms.RadioSelect,  # Esto hará que se muestre como radio buttons
        label="Estado de validación"
    )
    motivo_rechazo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Obligatorio si rechaza el comprobante"
    )
    
    class Meta:
        model = ComprobantePago
        fields = ['estado', 'motivo_rechazo']
    
    def clean(self):
        cleaned_data = super().clean()
        estado = cleaned_data.get('estado')
        motivo = cleaned_data.get('motivo_rechazo')
        
        if estado == 'R' and not motivo:
            raise forms.ValidationError("Debe especificar el motivo del rechazo")
        
        return cleaned_data

class RifasCaptchaForm(forms.Form):
    captcha_answer = forms.CharField(label="¿Cuánto es 3 + 4?")
    
    def clean_captcha_answer(self):
        answer = self.cleaned_data.get('captcha_answer')
        if answer.strip() != "7":
            raise forms.ValidationError("Respuesta incorrecta")
        return answer

class RifaForm(forms.ModelForm):
    class Meta:
        model = Rifa
        fields = ['nombre', 'fecha_sorteo', 'precio_boleto', 'boletos_total', 'premio_principal', 
                  'descripcion', 'imagen', 'activa']
        widgets = {
            'fecha_sorteo': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'premio_principal': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'precio_boleto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'boletos_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'imagen': forms.FileInput(attrs={'class': 'form-control'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre': 'Nombre de la Rifa',
            'fecha_sorteo': 'Fecha y Hora del Sorteo',
            'precio_boleto': 'Precio por Boleto',
            'boletos_total': 'Total de Boletos',
            'premio_principal': 'Premio Principal',
            'descripcion': 'Descripción',
            'imagen': 'Imagen de la Rifa',
            'activa': 'Rifa Activa',
        }
    
    def clean_boletos_total(self):
        boletos_total = self.cleaned_data.get('boletos_total')
        if boletos_total and boletos_total <= 0:
            raise forms.ValidationError("El total de boletos debe ser mayor a 0")
        return boletos_total
    
    def clean_precio_boleto(self):
        precio = self.cleaned_data.get('precio_boleto')
        if precio and precio <= 0:
            raise forms.ValidationError("El precio del boleto debe ser mayor a 0")
        return precio

class UsuarioCreateForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_staff = forms.BooleanField(
        required=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Usuario Administrador',
        help_text='Permite acceso al panel de administración'
    )
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Usuario Activo',
        initial=True
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'username': 'Nombre de Usuario',
            'email': 'Correo Electrónico',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'password1': 'Contraseña',
            'password2': 'Confirmar Contraseña',
        }
        help_texts = {
            'username': 'Requerido. 150 caracteres o menos. Solo letras, números y @/./+/-/_',
        }

class UsuarioEditForm(forms.ModelForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_staff = forms.BooleanField(
        required=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Usuario Administrador',
        help_text='Permite acceso al panel de administración'
    )
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Usuario Activo'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'username': 'Nombre de Usuario',
            'email': 'Correo Electrónico',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
        }

class UsuarioPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label='Nueva Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='La contraseña debe tener al menos 8 caracteres.'
    )
    new_password2 = forms.CharField(
        label='Confirmar Nueva Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("Las contraseñas no coinciden")
        return password2
    
    def save(self, commit=True):
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user