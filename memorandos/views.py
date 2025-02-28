from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Memorando
from auditoria.models import Auditoria
from datetime import datetime

@login_required
def memorandos_lista(request):
    from destinatarios.models import Destinatario  # Importamos aquí
    mostrar = request.GET.get('mostrar', 10)
    if mostrar == 'Todos':
        memorandos = Memorando.objects.all()
    else:
        memorandos = Memorando.objects.all()[:int(mostrar)]
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    destinatarios_predefinidos = Destinatario.objects.all()
    return render(request, 'memorandos/lista.html', {
        'memorandos': memorandos,
        'fecha_actual': fecha_actual,
        'destinatarios_predefinidos': destinatarios_predefinidos
    })

@login_required
def memorandos_agregar(request):
    if request.method == 'POST':
        data = request.POST
        fecha = data.get('fecha') or datetime.now().date()
        destinatario_select = data.get('destinatario_select')
        destinatario_custom = data.get('destinatario_custom', '').strip()
        destinatario = destinatario_custom if destinatario_select == "Otro" and destinatario_custom else destinatario_select
        memorando = Memorando(
            fecha=fecha,
            iddoc=data['iddoc'],
            destinatario=destinatario,
            materia=data['materia'],
            autor=request.user.username[:10]
        )
        memorando.save()
        Auditoria.objects.create(
            usuario=request.user, tipo='CREAR', tabla='memorandos',
            registro_id=memorando.pk, detalles=f'Creado {memorando.numero}'
        )
        return redirect('memorandos_lista')
    return redirect('memorandos_lista')

@login_required
def memorandos_editar(request, pk):
    memorando = get_object_or_404(Memorando, pk=pk)
    if memorando.autor != request.user.username[:10] and not request.user.is_staff:
        return redirect('memorandos_lista')
    if request.method == 'POST':
        memorando.fecha = request.POST['fecha']
        memorando.iddoc = request.POST['iddoc']
        memorando.destinatario = request.POST['destinatario']
        memorando.materia = request.POST['materia']
        memorando.save()
        Auditoria.objects.create(
            usuario=request.user, tipo='MODIFICAR', tabla='memorandos',
            registro_id=pk, detalles=f'Modificado {memorando.numero}'
        )
        return redirect('memorandos_lista')
    return render(request, 'memorandos/editar.html', {'memorando': memorando})

@login_required
def memorandos_anular(request, pk):
    memorando = get_object_or_404(Memorando, pk=pk)
    if memorando.autor != request.user.username[:10] and not request.user.is_staff:
        return redirect('memorandos_lista')
    memorando.anulada = True
    memorando.save()
    Auditoria.objects.create(
        usuario=request.user, tipo='ANULAR', tabla='memorandos',
        registro_id=pk, detalles=f'Anulado {memorando.numero}'
    )
    return redirect('memorandos_lista')