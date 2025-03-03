from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Ordinario, LibroConfig
from auditoria.models import Auditoria
from datetime import datetime

@login_required
def ordinarios_lista(request):
    from destinatarios.models import Destinatario
    mostrar = request.GET.get('mostrar', 10)
    if mostrar == 'Todos':
        ordinarios = Ordinario.objects.all()
    else:
        ordinarios = Ordinario.objects.all()[:int(mostrar)]
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    destinatarios_predefinidos = Destinatario.objects.all()
    config, created = LibroConfig.objects.get_or_create(id=1)
    return render(request, 'ordinarios/lista.html', {
        'ordinarios': ordinarios,
        'fecha_actual': fecha_actual,
        'destinatarios_predefinidos': destinatarios_predefinidos,
        'config': config,
        'active_tab': 'ordinarios',
    })

@login_required
def ordinarios_agregar(request):
    config = LibroConfig.objects.get(id=1)
    if config.bloqueado:
        messages.error(request, 'El libro está bloqueado. No se pueden agregar registros.')
        return redirect('ordinarios_lista')
    
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
                ultimo = Ordinario.objects.order_by('-numero').first()
                numero = (ultimo.numero + 1) if ultimo else 1
                
                registros = []
                for iddoc_str in iddoc_list:
                    iddoc = int(iddoc_str.replace('.', '')) if iddoc_str else None
                    ordinario = Ordinario(
                        numero=numero,
                        fecha=fecha,
                        iddoc=iddoc,
                        destinatario=destinatario,
                        materia=data['materia'],
                        autor=request.user.username[:10],
                        anulada=False,
                        redom=False
                    )
                    registros.append(ordinario)
                
                Ordinario.objects.bulk_create(registros)
                
                Auditoria.objects.create(
                    usuario=request.user, tipo='CREAR', tabla='ordinarios',
                    registro_id=numero, detalles=f'Creado ordinario {numero} con {len(registros)} entradas IDDOC'
                )
                messages.success(request, f'Ordinario {numero} agregado con {len(registros)} entradas IDDOC.')
        
        except ValueError as e:
            messages.error(request, f'Error en los datos: {str(e)}. Asegúrate de que "iddoc" sean números válidos separados por comas.')
        
        return redirect('ordinarios_lista')
    
    return redirect('ordinarios_lista')

@login_required
def ordinarios_editar(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    if ordinario.autor != request.user.username[:10] and not request.user.is_staff:
        messages.error(request, 'No tienes permiso para editar este ordinario.')
        return redirect('ordinarios_lista')
    
    if request.method == 'POST':
        data = request.POST
        try:
            ordinario.fecha = data['fecha']
            iddoc_str = data.get('iddoc', '').strip()
            ordinario.iddoc = int(iddoc_str.replace('.', '')) if iddoc_str else None
            ordinario.destinatario = data['destinatario']
            ordinario.materia = data['materia']
            ordinario.save()
            
            Auditoria.objects.create(
                usuario=request.user, tipo='MODIFICAR', tabla='ordinarios',
                registro_id=pk, detalles=f'Modificado ordinario {ordinario.numero}'
            )
            messages.success(request, f'Ordinario {ordinario.numero} editado correctamente.')
        except ValueError as e:
            messages.error(request, f'Error en los datos: {str(e)}. Asegúrate de que "iddoc" sea un número válido.')
        
        return redirect('ordinarios_lista')
    
    return render(request, 'ordinarios/lista.html', {
        'ordinario': ordinario,
        'active_tab': 'ordinarios',
    })

@login_required
def ordinarios_anular(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    usuario = request.user
    if ordinario.autor != usuario.username[:10] and not usuario.is_staff:
        messages.error(request, 'No tienes permiso para anular este ordinario.')
        return redirect('ordinarios_lista')
    
    if ordinario.anulada:
        ordinario.anulada = False
        accion = 'RESTAURAR'
        detalles = f'Restaurado ordinario #{ordinario.numero}'
    else:
        ordinario.anulada = True
        accion = 'ANULAR'
        detalles = f'Anulado ordinario #{ordinario.numero}'
    ordinario.save()
    Auditoria.objects.create(
        usuario=usuario, tipo=accion, tabla='ordinarios',
        registro_id=pk, detalles=detalles
    )
    messages.success(request, f'Ordinario {ordinario.numero} {accion.lower()}do correctamente.')
    return redirect('ordinarios_lista')

@login_required
def ordinarios_eliminar(request, pk):
    config = LibroConfig.objects.get(id=1)
    if config.bloqueado:
        messages.error(request, 'El libro está bloqueado. No se pueden eliminar registros.')
        return redirect('ordinarios_lista')
    
    ordinario = get_object_or_404(Ordinario, pk=pk)
    usuario = request.user
    if ordinario.autor != usuario.username[:10]:
        messages.error(request, 'No tienes permiso para eliminar este ordinario.')
        return redirect('ordinarios_lista')
    
    ultima_entrada = Ordinario.objects.filter(autor=usuario.username[:10]).order_by('-numero').first()
    if not ultima_entrada or ordinario.pk != ultima_entrada.pk:
        messages.error(request, 'Solo puedes eliminar la última entrada que creaste.')
        return redirect('ordinarios_lista')
    
    Auditoria.objects.create(
        usuario=usuario,
        tipo='ELIMINAR',
        tabla='ordinarios',
        registro_id=ordinario.pk,
        detalles=f'Eliminado ordinario #{ordinario.numero}'
    )
    ordinario.delete()
    messages.success(request, f'Ordinario {ordinario.numero} eliminado correctamente.')
    return redirect('ordinarios_lista')

@login_required
def ordinarios_bloquear(request):
    config, created = LibroConfig.objects.get_or_create(id=1)
    usuario = request.user
    if config.bloqueado:
        if config.bloqueado_por == usuario or usuario.is_staff:
            config.bloqueado = False
            config.bloqueado_por = None
            config.save()
            Auditoria.objects.create(
                usuario=usuario,
                tipo='DESBLOQUEAR',
                tabla='ordinarios',
                registro_id=1,
                detalles='Libro de ordinarios desbloqueado'
            )
            messages.success(request, 'Libro de ordinarios desbloqueado.')
    else:
        config.bloqueado = True
        config.bloqueado_por = usuario
        config.save()
        Auditoria.objects.create(
            usuario=usuario,
            tipo='BLOQUEAR',
            tabla='ordinarios',
            registro_id=1,
            detalles='Libro de ordinarios bloqueado'
        )
        messages.success(request, 'Libro de ordinarios bloqueado.')
    return redirect('ordinarios_lista')