from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Memorando, MemorandoConfig
from auditoria.models import Auditoria
from datetime import datetime

@login_required
def memorandos_lista(request):
    from destinatarios.models import Destinatario
    mostrar = request.GET.get('mostrar', 10)
    if mostrar == 'Todos':
        memorandos = Memorando.objects.all()
    else:
        memorandos = Memorando.objects.all()[:int(mostrar)]
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    destinatarios_predefinidos = Destinatario.objects.all()
    config, created = MemorandoConfig.objects.get_or_create(id=1)
    return render(request, 'memorandos/lista.html', {
        'memorandos': memorandos,
        'fecha_actual': fecha_actual,
        'destinatarios_predefinidos': destinatarios_predefinidos,
        'config': config,
        'active_tab': 'memorandos',
    })

@login_required
def memorandos_agregar(request):
    config = MemorandoConfig.objects.get(id=1)
    if config.bloqueado:
        messages.error(request, 'El libro está bloqueado. No se pueden agregar registros.')
        return redirect('memorandos_lista')
    
    if request.method == 'POST':
        data = request.POST
        fecha = data.get('fecha') or datetime.now().date()
        destinatario_select = data.get('destinatario_select')
        destinatario_custom = data.get('destinatario_custom', '').strip()
        destinatario = destinatario_custom if destinatario_select == "Otro" and destinatario_custom else destinatario_select
        
        # Procesar iddoc como lista separada por comas (con o sin espacios)
        iddoc_input = data.get('iddoc', '').strip()
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()]
        
        try:
            with transaction.atomic():
                ultimo = Memorando.objects.order_by('-numero').first()
                numero = (ultimo.numero + 1) if ultimo else 1
                
                registros = []
                for iddoc_str in iddoc_list:
                    iddoc = int(iddoc_str.replace('.', '')) if iddoc_str else None
                    memorando = Memorando(
                        numero=numero,
                        fecha=fecha,
                        iddoc=iddoc,
                        destinatario=destinatario,
                        materia=data['materia'],
                        autor=request.user.username[:10],
                        anulada=False,
                        redom=False
                    )
                    registros.append(memorando)
                
                Memorando.objects.bulk_create(registros)
                
                Auditoria.objects.create(
                    usuario=request.user, tipo='CREAR', tabla='memorandos',
                    registro_id=numero, detalles=f'Creado memorando {numero} con {len(registros)} entradas IDDOC'
                )
                messages.success(request, f'Memorando {numero} agregado con {len(registros)} entradas IDDOC.')
        
        except ValueError as e:
            messages.error(request, f'Error en los datos: {str(e)}. Asegúrate de que "iddoc" sean números válidos separados por comas.')
        
        return redirect('memorandos_lista')
    
    return redirect('memorandos_lista')

@login_required
def memorandos_editar(request, pk):
    memorando = get_object_or_404(Memorando, pk=pk)
    if memorando.autor != request.user.username[:10] and not request.user.is_staff:
        messages.error(request, 'No tienes permiso para editar este memorando.')
        return redirect('memorandos_lista')
    
    if request.method == 'POST':
        data = request.POST
        try:
            memorando.fecha = data['fecha']
            iddoc_str = data.get('iddoc', '').strip()
            memorando.iddoc = int(iddoc_str.replace('.', '')) if iddoc_str else None
            memorando.destinatario = data['destinatario']
            memorando.materia = data['materia']
            memorando.save()
            
            Auditoria.objects.create(
                usuario=request.user, tipo='MODIFICAR', tabla='memorandos',
                registro_id=pk, detalles=f'Modificado memorando {memorando.numero}'
            )
            messages.success(request, f'Memorando {memorando.numero} editado correctamente.')
        except ValueError as e:
            messages.error(request, f'Error en los datos: {str(e)}. Asegúrate de que "iddoc" sea un número válido.')
        
        return redirect('memorandos_lista')
    
    return render(request, 'memorandos/lista.html', {
        'memorando': memorando,
        'active_tab': 'memorandos',
    })

@login_required
def memorandos_anular(request, pk):
    memorando = get_object_or_404(Memorando, pk=pk)
    usuario = request.user
    if memorando.autor != usuario.username[:10] and not usuario.is_staff:
        messages.error(request, 'No tienes permiso para anular este memorando.')
        return redirect('memorandos_lista')
    
    if memorando.anulada:
        memorando.anulada = False
        accion = 'RESTAURAR'
        detalles = f'Restaurado memorando #{memorando.numero}'
    else:
        memorando.anulada = True
        accion = 'ANULAR'
        detalles = f'Anulado memorando #{memorando.numero}'
    memorando.save()
    Auditoria.objects.create(
        usuario=usuario, tipo=accion, tabla='memorandos',
        registro_id=pk, detalles=detalles
    )
    messages.success(request, f'Memorando {memorando.numero} {accion.lower()}do correctamente.')
    return redirect('memorandos_lista')

@login_required
def memorandos_bloquear(request):
    config, created = MemorandoConfig.objects.get_or_create(id=1)
    usuario = request.user
    if config.bloqueado:
        if config.bloqueado_por == usuario or usuario.is_staff:
            config.bloqueado = False
            config.bloqueado_por = None
            config.save()
            Auditoria.objects.create(
                usuario=usuario,
                tipo='DESBLOQUEAR',
                tabla='memorandos',
                registro_id=1,
                detalles='Libro de memorandos desbloqueado'
            )
            messages.success(request, 'Libro de memorandos desbloqueado.')
    else:
        config.bloqueado = True
        config.bloqueado_por = usuario
        config.save()
        Auditoria.objects.create(
            usuario=usuario,
            tipo='BLOQUEAR',
            tabla='memorandos',
            registro_id=1,
            detalles='Libro de memorandos bloqueado'
        )
        messages.success(request, 'Libro de memorandos bloqueado.')
    return redirect('memorandos_lista')