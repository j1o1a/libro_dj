from django import forms
from .models import Memorando
import datetime

class MemorandoForm(forms.ModelForm):
    class Meta:
        model = Memorando
        fields = ['fecha', 'iddoc', 'destinatario', 'materia']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'destinatario': forms.TextInput(attrs={'autocomplete': 'off'}),
            'materia': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].initial = datetime.date.today