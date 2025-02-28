from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Memorando
from auditoria.models import Auditoria
from django.http import JsonResponse

@login_required
def memorandos_lista(request):
    mostrar = request.GET.get('mostrar', 10)
    if mostrar == 'Todos':
        memorandos = Memorando.objects.all()
    else:
        memorandos = Memorando.objects.all()[:int(mostrar)]
    return render(request, 'memorandos/lista.html', {'memorandos': memorandos})

@login_required
def memorandos_agregar(request):
    if request.method == 'POST':
        data = request.POST
        memorando = Memorando(
            fecha=data['fecha'],
            iddoc=data['iddoc'],
            destinatario=data['destinatario'],
            materia=data['materia'],
            autor=request.user.username[:10]  # Iniciales del usuario autenticado
        )
        memorando.save()
        Auditoria.objects.create(
            usuario=request.user, tipo='CREAR', tabla='memorandos',
            registro_id=memorando.pk, detalles=f'Creado {memorando.numero}'
        )
        return redirect('memorandos_lista')
    return JsonResponse({'html': render(request, 'memorandos/form.html').content.decode()})

@login_required
def memorandos_editar(request, pk):
    memorando = get_object_or_404(Memorando, pk=pk)
    # Solo el autor o un admin puede editar
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
    # Solo el autor o un admin puede anular
    if memorando.autor != request.user.username[:10] and not request.user.is_staff:
        return redirect('memorandos_lista')
    memorando.anulada = True
    memorando.save()
    Auditoria.objects.create(
        usuario=request.user, tipo='ANULAR', tabla='memorandos',
            registro_id=pk, detalles=f'Anulado {memorando.numero}'
    )
    return redirect('memorandos_lista')