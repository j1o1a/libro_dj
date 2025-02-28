from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Ordinario
from auditoria.models import Auditoria
from datetime import datetime

@login_required
def ordinarios_lista(request):
    mostrar = request.GET.get('mostrar', 10)
    if mostrar == 'Todos':
        ordinarios = Ordinario.objects.all()
    else:
        ordinarios = Ordinario.objects.all()[:int(mostrar)]
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    return render(request, 'ordinarios/lista.html', {'ordinarios': ordinarios, 'fecha_actual': fecha_actual})

@login_required
def ordinarios_agregar(request):
    if request.method == 'POST':
        data = request.POST
        # Si no hay fecha en el POST, usamos la fecha actual
        fecha = data.get('fecha')
        if not fecha:  # Si está vacía o no se envió
            fecha = datetime.now().date()  # Usamos .date() para coincidir con DateField
        ordinario = Ordinario(
            fecha=fecha,
            iddoc=data['iddoc'],
            destinatario=data['destinatario'],
            materia=data['materia'],
            autor=request.user.username[:10]
        )
        ordinario.save()
        Auditoria.objects.create(
            usuario=request.user, tipo='CREAR', tabla='ordinarios',
            registro_id=ordinario.pk, detalles=f'Creado {ordinario.numero}'
        )
        return redirect('ordinarios_lista')
    return redirect('ordinarios_lista')

@login_required
def ordinarios_editar(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    if ordinario.autor != request.user.username[:10] and not request.user.is_staff:
        return redirect('ordinarios_lista')
    if request.method == 'POST':
        ordinario.fecha = request.POST['fecha']
        ordinario.iddoc = request.POST['iddoc']
        ordinario.destinatario = request.POST['destinatario']
        ordinario.materia = request.POST['materia']
        ordinario.save()
        Auditoria.objects.create(
            usuario=request.user, tipo='MODIFICAR', tabla='ordinarios',
            registro_id=pk, detalles=f'Modificado {ordinario.numero}'
        )
        return redirect('ordinarios_lista')
    return render(request, 'ordinarios/editar.html', {'ordinario': ordinario})

@login_required
def ordinarios_anular(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    if ordinario.autor != request.user.username[:10] and not request.user.is_staff:
        return redirect('ordinarios_lista')
    ordinario.anulada = True
    ordinario.save()
    Auditoria.objects.create(
        usuario=request.user, tipo='ANULAR', tabla='ordinarios',
        registro_id=pk, detalles=f'Anulado {ordinario.numero}'
    )
    return redirect('ordinarios_lista')