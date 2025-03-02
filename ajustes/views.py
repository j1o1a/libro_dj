from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
from django.contrib import messages
from django.db import transaction
from ordinarios.models import Ordinario
from memorandos.models import Memorando
import csv
from io import TextIOWrapper
from datetime import datetime

class CSVUploadForm(forms.Form):
    TABLE_CHOICES = (
        ('ordinarios', 'Ordinarios'),
        ('memorandos', 'Memorandos'),
    )
    csv_file = forms.FileField(label="Archivo CSV", widget=forms.FileInput(attrs={'accept': '.csv'}))
    table = forms.ChoiceField(choices=TABLE_CHOICES, label="Importar a", widget=forms.Select(attrs={'class': 'form-select'}))

@login_required
@user_passes_test(lambda u: u.is_staff)
def ajustes(request):
    form = CSVUploadForm()
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            table = form.cleaned_data['table']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'El archivo debe ser un CSV.')
                return render(request, 'ajustes/ajustes.html', {
                    'title': 'Ajustes',
                    'active_tab': 'ajustes',
                    'form': form,
                })
            
            try:
                csv_data = TextIOWrapper(csv_file.file, encoding='utf-8')
                reader = csv.DictReader(csv_data, delimiter=';')
                
                required_headers = {'numero', 'fecha', 'iddoc', 'destinatario', 'materia', 'iniciales', 'redom'}
                csv_headers = {header.strip().lower() for header in reader.fieldnames}
                if not required_headers.issubset(csv_headers):
                    messages.error(request, 'El CSV debe contener las columnas: numero, fecha, iddoc, destinatario, materia, iniciales, redom.')
                    return render(request, 'ajustes/ajustes.html', {
                        'title': 'Ajustes',
                        'active_tab': 'ajustes',
                        'form': form,
                    })
                
                model = Ordinario if table == 'ordinarios' else Memorando
                
                with transaction.atomic():
                    model.objects.all().delete()
                    registros = []
                    for row in reader:
                        numero = int(row['numero'])
                        fecha = datetime.strptime(row['fecha'], '%d-%m-%y').date()
                        iddoc = int(row['iddoc'].replace('.', '')) if row['iddoc'] else None
                        redom = row['redom'] != ''
                        
                        registros.append(model(
                            numero=numero,
                            fecha=fecha,
                            iddoc=iddoc,
                            destinatario=row['destinatario'],
                            materia=row['materia'],
                            autor=row['iniciales'],
                            anulada=False,
                            redom=redom,
                        ))
                    
                    model.objects.bulk_create(registros)
                
                messages.success(request, f'Se importaron {len(registros)} registros a {table} correctamente.')
            except ValueError as e:
                messages.error(request, f'Error en los datos del CSV: {str(e)}. Asegúrate de que "numero", "iddoc" y "redom" sean válidos y "fecha" esté en formato dd-mm-aa.')
            except Exception as e:
                messages.error(request, f'Error al procesar el CSV: {str(e)}')
            
            return render(request, 'ajustes/ajustes.html', {
                'title': 'Ajustes',
                'active_tab': 'ajustes',
                'form': form,
            })
    
    return render(request, 'ajustes/ajustes.html', {
        'title': 'Ajustes',
        'active_tab': 'ajustes',
        'form': form,
    })