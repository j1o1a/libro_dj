from django import forms
from .models import Ordinario
import datetime

class OrdinarioForm(forms.ModelForm):
    class Meta:
        model = Ordinario
        fields = ['fecha', 'iddoc', 'destinatario', 'materia']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'destinatario': forms.TextInput(attrs={'autocomplete': 'off'}),
            'materia': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].initial = datetime.date.today