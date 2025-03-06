from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Ordinario, LibroConfig
from auditoria.models import Auditoria
from datetime import datetime

@login_required
def ordinarios_lista(request):
    from destinatarios.models import Destinatario
    
    # Obtener el número de ítems por página desde el request (default=10)
    items_per_page = request.GET.get('items_per_page', '10')  # Cambiado a cadena '10'
    
    # Obtener todos los ordinarios, ordenados por número descendente
    ordinarios_list = Ordinario.objects.all().order_by('-numero')
    
    # Si se selecciona "Todos", no paginar
    if items_per_page == 'all':
        paginated_ordinarios = ordinarios_list
        page_obj = None  # No hay paginación
    else:
        # Convertir items_per_page a entero para el Paginator, fallback a 10 si falla
        try:
            items_per_page_int = int(items_per_page)
        except (ValueError, TypeError):
            items_per_page_int = 10
            items_per_page = '10'  # Aseguramos que items_per_page sea cadena
        
        # Crear el objeto Paginator
        paginator = Paginator(ordinarios_list, items_per_page_int)
        
        # Obtener el número de página desde el request
        page = request.GET.get('page', 1)
        
        try:
            paginated_ordinarios = paginator.page(page)
        except PageNotAnInteger:
            paginated_ordinarios = paginator.page(1)
        except EmptyPage:
            paginated_ordinarios = paginator.page(paginator.num_pages)
        
        page_obj = paginated_ordinarios
    
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    destinatarios_predefinidos = Destinatario.objects.all()
    config, created = LibroConfig.objects.get_or_create(id=1)
    
    return render(request, 'ordinarios/lista.html', {
        'ordinarios': paginated_ordinarios,
        'page_obj': page_obj,
        'items_per_page': str(items_per_page),
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
        materia = data.get('materia', '').strip()
        iddoc_input = data.get('iddoc', '').strip()
        
        # Validar que destinatario_custom no esté vacío si se seleccionó "Otro"
        if destinatario_select == "Otro" and not destinatario_custom:
            messages.error(request, 'Por favor, especifique un destinatario personalizado.')
            return render(request, 'ordinarios/lista.html', {
                'ordinarios': Ordinario.objects.all(),
                'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
                'destinatarios_predefinidos': Destinatario.objects.all(),
                'config': config,
                'active_tab': 'ordinarios',
                'form_data': data,
            })
        
        # Determinar el valor final de destinatario
        destinatario = destinatario_custom if destinatario_select == "Otro" else destinatario_select
        
        # Procesar los valores de iddoc
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()]
        
        try:
            with transaction.atomic():
                ultimo = Ordinario.objects.order_by('-numero').first()
                numero = (ultimo.numero + 1) if ultimo else 1
                
                registros = []
                # Si no se proporcionaron valores de iddoc, crear un registro con iddoc=None
                if not iddoc_list:
                    ordinario = Ordinario(
                        numero=numero,
                        fecha=fecha,
                        iddoc=None,
                        destinatario=destinatario,
                        materia=materia,
                        autor=request.user.username[:10],
                        anulada=False,
                        redom=False
                    )
                    registros.append(ordinario)
                else:
                    # Crear un registro por cada iddoc proporcionado
                    for iddoc_str in iddoc_list:
                        iddoc = int(iddoc_str.replace('.', '')) if iddoc_str else None
                        ordinario = Ordinario(
                            numero=numero,
                            fecha=fecha,
                            iddoc=iddoc,
                            destinatario=destinatario,
                            materia=materia,
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