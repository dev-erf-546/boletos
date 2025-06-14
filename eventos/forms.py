from django import forms
from .models import Participante, ComprobantePago

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