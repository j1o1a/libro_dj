from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction
from django.contrib import messages
from django.urls import reverse
from datetime import datetime
from ordinarios.models import Ordinario, LibroConfig
from destinatarios.models import Destinatario
from auditoria.models import Auditoria
from django.core.cache import cache
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Función auxiliar optimizada para calcular la página de un ordinario
def get_page_for_ordinario(ordinario, items_per_page, total_count, ordinarios_list):
    items_per_page_int = int(items_per_page) if items_per_page != 'all' else total_count
    
    # Calcular count_before usando ordinarios_list para evitar consultas adicionales
    count_before = 0
    for o in ordinarios_list:
        if o.numero > ordinario.numero or (o.numero == ordinario.numero and o.pk > ordinario.pk):
            count_before += 1
    
    page = (count_before // items_per_page_int) + 1 if count_before > 0 else 1
    return page

@login_required
def ordinarios_lista(request):
    items_per_page = request.GET.get('items_per_page', '10')
    page = request.GET.get('page', '1')
    
    # Determinar el número de registros por página y obtener el conteo total
    total_count = Ordinario.objects.count()  # Hacer el conteo una sola vez
    if items_per_page == 'all':
        items_per_page_int = total_count
    else:
        try:
            items_per_page_int = int(items_per_page)
        except (ValueError, TypeError):
            items_per_page_int = 10
            items_per_page = '10'
    
    # Paginación inicial para determinar el rango de registros a cargar
    all_ordinarios = Ordinario.objects.only('pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom').order_by('-numero', '-creada')
    paginator = Paginator(all_ordinarios, items_per_page_int)
    
    try:
        paginated_ordinarios = paginator.page(page)
    except PageNotAnInteger:
        paginated_ordinarios = paginator.page(1)
    except EmptyPage:
        paginated_ordinarios = paginator.page(paginator.num_pages)
    
    page_obj = paginated_ordinarios
    
    # Determinar los números (numero) presentes en la página actual
    visible_numbers = list(set(o.numero for o in paginated_ordinarios))
    
    # Cargar todos los registros correspondientes a los números visibles
    ordinarios_list = list(
        Ordinario.objects.only('pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom')
        .filter(numero__in=visible_numbers)
        .order_by('-numero', '-creada')
    )
    
    # Construir grupos_datos y calcular atributos para los números visibles
    grupos_datos = {}
    latest_entries = {}
    first_entries = {}
    last_entries = {}
    es_multiple_dict = {}
    current_numero = None
    items_for_numero = []
    
    for o in ordinarios_list:
        if o.numero != current_numero:
            if current_numero is not None:
                latest_entry = max(items_for_numero, key=lambda x: (x.creada or datetime.min, x.pk))
                first_entry = items_for_numero[0]
                last_entry = items_for_numero[-1]
                latest_entries[current_numero] = latest_entry.pk
                first_entries[current_numero] = first_entry.pk
                last_entries[current_numero] = last_entry.pk
                unique_iddocs = set(obj.iddoc for obj in items_for_numero if obj.iddoc)
                unique_destinatarios = set(obj.destinatario for obj in items_for_numero)
                es_multiple_dict[current_numero] = len(unique_iddocs) > 1 or len(unique_destinatarios) > 1
                grupos_datos[current_numero] = {
                    'iddocs': ", ".join(str(iddoc) for iddoc in sorted(unique_iddocs)),
                    'destinatarios': ", ".join(unique_destinatarios),
                    'materia': items_for_numero[0].materia,
                    'fecha': items_for_numero[0].fecha.strftime('%Y-%m-%d') if items_for_numero[0].fecha else '',
                }
            current_numero = o.numero
            items_for_numero = [o]
        else:
            items_for_numero.append(o)
    
    # Procesar el último grupo
    if current_numero is not None and items_for_numero:
        latest_entry = max(items_for_numero, key=lambda x: (x.creada or datetime.min, x.pk))
        first_entry = items_for_numero[0]
        last_entry = items_for_numero[-1]
        latest_entries[current_numero] = latest_entry.pk
        first_entries[current_numero] = first_entry.pk
        last_entries[current_numero] = last_entry.pk
        unique_iddocs = set(obj.iddoc for obj in items_for_numero if obj.iddoc)
        unique_destinatarios = set(obj.destinatario for obj in items_for_numero)
        es_multiple_dict[current_numero] = len(unique_iddocs) > 1 or len(unique_destinatarios) > 1
        grupos_datos[current_numero] = {
            'iddocs': ", ".join(str(iddoc) for iddoc in sorted(unique_iddocs)),
            'destinatarios': ", ".join(unique_destinatarios),
            'materia': items_for_numero[0].materia,
            'fecha': items_for_numero[0].fecha.strftime('%Y-%m-%d') if items_for_numero[0].fecha else '',
        }
    
    # Asignar atributos a los objetos visibles
    for o in paginated_ordinarios:
        o.es_mas_reciente = (o.pk == latest_entries.get(o.numero))
        o.es_multiple = es_multiple_dict.get(o.numero, False)
        o.is_first_in_group = (o.pk == first_entries.get(o.numero))
        o.is_last_in_group = (o.pk == last_entries.get(o.numero))
    
    # Preprocesar datos para modales de edición con destinatarios únicos
    edit_data = {}
    for numero in visible_numbers:
        entries = [o for o in ordinarios_list if o.numero == numero]
        unique_destinatarios = [{'destinatario': destinatario} for destinatario in set(o.destinatario for o in entries)]
        edit_data[numero] = unique_destinatarios
        logger.debug(f"Destinatarios para ordinario {numero}: {[d['destinatario'] for d in unique_destinatarios]}")
    
    # Usar caché para destinatarios_dentro y destinatarios_fuera
    cache_key = 'destinatarios_ordinarios'
    destinatarios_cached = cache.get(cache_key)
    if destinatarios_cached is None:
        destinatarios_dentro = list(Destinatario.objects.filter(es_municipio=True).order_by('orden'))
        destinatarios_fuera = list(Destinatario.objects.filter(es_municipio=False).order_by('orden'))
        cache.set(cache_key, {'dentro': destinatarios_dentro, 'fuera': destinatarios_fuera}, timeout=3600)
    else:
        destinatarios_dentro = destinatarios_cached['dentro']
        destinatarios_fuera = destinatarios_cached['fuera']
    
    # Consultar config con select_related para bloqueado_por
    config, created = LibroConfig.objects.select_related('bloqueado_por').get_or_create(id=1)
    
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    
    return render(request, 'ordinarios/lista.html', {
        'ordinarios': paginated_ordinarios,
        'page_obj': page_obj,
        'items_per_page': str(items_per_page),
        'fecha_actual': fecha_actual,
        'destinatarios_dentro': destinatarios_dentro,
        'destinatarios_fuera': destinatarios_fuera,
        'config': config,
        'active_tab': 'ordinarios',
        'grupos_datos': grupos_datos,
        'edit_data': edit_data,
        'total_count': total_count,
    })

@login_required
def ordinarios_bloquear(request):
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    items_per_page = request.GET.get('items_per_page', '10')
    total_count = Ordinario.objects.count()
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        return render(request, 'ordinarios/lista.html', {
            'ordinarios': Ordinario.objects.only('pk', 'numero'),
            'items_per_page': items_per_page,
            'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
            'destinatarios_dentro': cache.get_or_set('destinatarios_ordinarios_dentro', list(Destinatario.objects.filter(es_municipio=True).order_by('orden')), timeout=3600),
            'destinatarios_fuera': cache.get_or_set('destinatarios_ordinarios_fuera', list(Destinatario.objects.filter(es_municipio=False).order_by('orden')), timeout=3600),
            'config': config,
            'active_tab': 'ordinarios',
            'show_blocked_modal': True,
            'total_count': total_count,
        })
    
    if request.method == 'POST':
        config.bloqueado = not config.bloqueado
        config.bloqueado_por = request.user if config.bloqueado else None
        config.save()
        
        accion = 'BLOQUEADO' if config.bloqueado else 'DESBLOQUEADO'
        Auditoria.objects.create(
            usuario=request.user,
            tipo=accion,
            tabla='libro_config',
            registro_id=1,
            detalles=f'Libro de ordinarios {accion.lower()} por {request.user.username}'
        )
        messages.success(request, f'Libro de ordinarios {"bloqueado" if config.bloqueado else "desbloqueado"} correctamente.')
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")

@login_required
def ordinarios_agregar(request):
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    items_per_page = request.GET.get('items_per_page', '10')
    total_count = Ordinario.objects.count()
    ordinarios_list = list(Ordinario.objects.only('pk', 'numero', 'creada').order_by('-numero', '-creada'))
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        messages.error(request, 'El libro está bloqueado. No se pueden agregar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if request.method == 'POST':
        data = request.POST
        fecha = data.get('fecha') or datetime.now().date()
        materia = data.get('materia', '').strip()
        iddoc_input = data.get('iddoc', '').strip()
        
        # Procesar múltiples destinatarios
        destinatarios = []
        i = 1
        while True:
            select_key = f'destinatario_select_{i}'
            custom_key = f'destinatario_custom_{i}'
            if select_key not in data:
                break
            select_values = data.getlist(f'destinatario_select_{i}')  # Obtener todos los valores para la clave
            custom_value = data.get(custom_key, '').strip()
            for select_value in select_values:
                select_value = select_value.strip()
                if select_value in ['Otro_Dentro', 'Otro_Fuera']:
                    if not custom_value:
                        messages.error(request, f'Por favor, especifique un destinatario personalizado para el campo #{i}.')
                        return render(request, 'ordinarios/lista.html', {
                            'ordinarios': Ordinario.objects.only('pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom'),
                            'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
                            'destinatarios_dentro': cache.get_or_set('destinatarios_ordinarios_dentro', list(Destinatario.objects.filter(es_municipio=True).order_by('orden')), timeout=3600),
                            'destinatarios_fuera': cache.get_or_set('destinatarios_ordinarios_fuera', list(Destinatario.objects.filter(es_municipio=False).order_by('orden')), timeout=3600),
                            'config': config,
                            'active_tab': 'ordinarios',
                            'form_data': data,
                            'items_per_page': items_per_page,
                            'total_count': total_count,
                            'ordinarios_list': ordinarios_list,
                        })
                    destinatarios.append(custom_value)
                elif select_value:
                    destinatarios.append(select_value)
            i += 1
        
        # Eliminar duplicados en destinatarios
        destinatarios = list(dict.fromkeys(destinatarios))
        
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()] or [None]
        
        try:
            with transaction.atomic():
                ultimo = Ordinario.objects.select_for_update().order_by('-numero').first()
                numero = (ultimo.numero + 1) if ultimo else 1
                
                registros = []
                for destinatario in destinatarios:
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
                    registro_id=numero, detalles=f'Creado ordinario {numero} con {len(registros)} entradas (IDDOC x Destinatarios)'
                )
                messages.success(request, f'Ordinario {numero} agregado con {len(registros)} entradas.')
        
        except ValueError as e:
            messages.error(request, f'Error en los datos: {str(e)}. Asegúrate de que "iddoc" sean números válidos separados por comas.')
        
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")

@login_required
def ordinarios_editar(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    items_per_page = request.GET.get('items_per_page', '10')
    page = request.GET.get('page', '1')
    grupo_ordinarios = Ordinario.objects.filter(numero=ordinario.numero).order_by('-creada')
    
    if request.method == 'POST':
        data = request.POST
        logger.debug(f"Datos recibidos del formulario: {data}")
        
        fecha = data.get('fecha')
        iddoc_input = data.get('iddoc', '').strip()
        materia = data.get('materia', '').strip()
        
        # Procesar iddoc
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()] or [None]
        iddoc_list = list(dict.fromkeys([int(idd.replace('.', '')) if idd else None for idd in iddoc_list]))  # Convertir a int o None y eliminar duplicados
        
        # Procesar destinatarios
        destinatarios = []
        for key in data.keys():
            if key.startswith('destinatario_select_'):
                index = int(key.split('_')[-1])
                select_values = data.getlist(key)  # Obtener todos los valores para la clave
                custom_value = data.get(f'destinatario_custom_{index}', '').strip()
                logger.debug(f"Procesando {key}: select_values={select_values}, custom_value={custom_value}")
                for select_value in select_values:
                    select_value = select_value.strip()
                    if select_value in ['Otro_Dentro', 'Otro_Fuera'] and custom_value:
                        destinatarios.append(custom_value)
                    elif select_value:
                        destinatarios.append(select_value)
        
        logger.debug(f"Destinatarios procesados antes de validación: {destinatarios}")
        
        # Calcular total_count dentro del bloque POST
        total_count = Ordinario.objects.count()
        ordinarios_list = list(
            Ordinario.objects.only('pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom')
            .order_by('-numero', '-creada')
        )
        
        # Validar que haya al menos un destinatario
        if not destinatarios:
            messages.error(request, 'Debe especificar al menos un destinatario.')
            form_data = {
                'fecha': fecha,
                'iddoc': ", ".join(str(idd) for idd in iddoc_list if idd is not None),
                'materia': materia,
                'destinatarios': [{'select_value': d, 'custom_value': ''} for d in set(destinatarios) if d] if destinatarios else [],
            }
            # Renderizar lista.html con el modal abierto y datos preservados
            paginator = Paginator(ordinarios_list, int(items_per_page) if items_per_page != 'all' else total_count)
            try:
                paginated_ordinarios = paginator.page(page)
            except PageNotAnInteger:
                paginated_ordinarios = paginator.page(1)
            except EmptyPage:
                paginated_ordinarios = paginator.page(paginator.num_pages)
            
            page_obj = paginated_ordinarios  # Definir page_obj aquí
            
            visible_numbers = list(set(o.numero for o in paginated_ordinarios))
            ordinarios_list_filtered = [o for o in ordinarios_list if o.numero in visible_numbers]
            grupos_datos = {}
            latest_entries = {}
            first_entries = {}
            last_entries = {}
            es_multiple_dict = {}
            current_numero = None
            items_for_numero = []
            
            for o in ordinarios_list_filtered:
                if o.numero != current_numero:
                    if current_numero is not None:
                        latest_entry = max(items_for_numero, key=lambda x: (x.creada or datetime.min, x.pk))
                        first_entry = items_for_numero[0]
                        last_entry = items_for_numero[-1]
                        latest_entries[current_numero] = latest_entry.pk
                        first_entries[current_numero] = first_entry.pk
                        last_entries[current_numero] = last_entry.pk
                        unique_iddocs = set(obj.iddoc for obj in items_for_numero if obj.iddoc)
                        unique_destinatarios = set(obj.destinatario for obj in items_for_numero)
                        es_multiple_dict[current_numero] = len(unique_iddocs) > 1 or len(unique_destinatarios) > 1
                        grupos_datos[current_numero] = {
                            'iddocs': ", ".join(str(iddoc) for iddoc in sorted(unique_iddocs)),
                            'destinatarios': ", ".join(unique_destinatarios),
                            'materia': items_for_numero[0].materia,
                            'fecha': items_for_numero[0].fecha.strftime('%Y-%m-%d') if items_for_numero[0].fecha else '',
                        }
                    current_numero = o.numero
                    items_for_numero = [o]
                else:
                    items_for_numero.append(o)
            
            if current_numero is not None and items_for_numero:
                latest_entry = max(items_for_numero, key=lambda x: (x.creada or datetime.min, x.pk))
                first_entry = items_for_numero[0]
                last_entry = items_for_numero[-1]
                latest_entries[current_numero] = latest_entry.pk
                first_entries[current_numero] = first_entry.pk
                last_entries[current_numero] = last_entry.pk
                unique_iddocs = set(obj.iddoc for obj in items_for_numero if obj.iddoc)
                unique_destinatarios = set(obj.destinatario for obj in items_for_numero)
                es_multiple_dict[current_numero] = len(unique_iddocs) > 1 or len(unique_destinatarios) > 1
                grupos_datos[current_numero] = {
                    'iddocs': ", ".join(str(iddoc) for iddoc in sorted(unique_iddocs)),
                    'destinatarios': ", ".join(unique_destinatarios),
                    'materia': items_for_numero[0].materia,
                    'fecha': items_for_numero[0].fecha.strftime('%Y-%m-%d') if items_for_numero[0].fecha else '',
                }
            
            for o in paginated_ordinarios:
                o.es_mas_reciente = (o.pk == latest_entries.get(o.numero))
                o.es_multiple = es_multiple_dict.get(o.numero, False)
                o.is_first_in_group = (o.pk == first_entries.get(o.numero))
                o.is_last_in_group = (o.pk == last_entries.get(o.numero))
            
            edit_data = {}
            for numero in visible_numbers:
                entries = [o for o in ordinarios_list_filtered if o.numero == numero]
                unique_destinatarios = [{'destinatario': destinatario} for destinatario in set(o.destinatario for o in entries)]
                edit_data[numero] = unique_destinatarios
            
            cache_key = 'destinatarios_ordinarios'
            destinatarios_cached = cache.get(cache_key)
            if destinatarios_cached is None:
                destinatarios_dentro = list(Destinatario.objects.filter(es_municipio=True).order_by('orden'))
                destinatarios_fuera = list(Destinatario.objects.filter(es_municipio=False).order_by('orden'))
                cache.set(cache_key, {'dentro': destinatarios_dentro, 'fuera': destinatarios_fuera}, timeout=3600)
            else:
                destinatarios_dentro = destinatarios_cached['dentro']
                destinatarios_fuera = destinatarios_cached['fuera']
            
            config, created = LibroConfig.objects.select_related('bloqueado_por').get_or_create(id=1)
            fecha_actual = datetime.now().strftime('%Y-%m-%d')
            
            return render(request, 'ordinarios/lista.html', {
                'ordinarios': paginated_ordinarios,
                'page_obj': page_obj,
                'items_per_page': items_per_page,
                'fecha_actual': fecha_actual,
                'destinatarios_dentro': destinatarios_dentro,
                'destinatarios_fuera': destinatarios_fuera,
                'config': config,
                'active_tab': 'ordinarios',
                'grupos_datos': grupos_datos,
                'edit_data': edit_data,
                'total_count': total_count,
                'form_data': form_data,
                'show_edit_modal': ordinario.numero,
            })
        
        # Eliminar duplicados en destinatarios
        destinatarios = list(dict.fromkeys(destinatarios))  # Convierte a lista con elementos únicos
        
        # Crear combinaciones únicas de iddoc y destinatarios
        registros = []
        seen_combinations = set()
        for iddoc in iddoc_list:
            for destinatario in destinatarios:
                combination = (iddoc, destinatario)
                if combination not in seen_combinations:
                    seen_combinations.add(combination)
                    ordinario_new = Ordinario(
                        numero=ordinario.numero,
                        fecha=fecha,
                        iddoc=iddoc,
                        destinatario=destinatario,
                        materia=materia,
                        autor=ordinario.autor,
                        creada=ordinario.creada
                    )
                    registros.append(ordinario_new)
        
        with transaction.atomic():
            grupo_ordinarios.delete()  # Eliminar todas las entradas existentes
            Ordinario.objects.bulk_create(registros)
        
        messages.success(request, f'Ordinario {ordinario.numero} editado correctamente.')
        page = get_page_for_ordinario(ordinario, items_per_page, total_count, ordinarios_list)
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&page={page}#ordinario-{ordinario.pk}")
    
    # Inicializar con iddocs y destinatarios únicos
    unique_iddocs = sorted(set(o.iddoc for o in grupo_ordinarios if o.iddoc))
    iddocs = ", ".join(str(iddoc) for iddoc in unique_iddocs)
    unique_destinatarios = set(o.destinatario for o in grupo_ordinarios)
    destinatarios = ", ".join(unique_destinatarios)
    return render(request, 'ordinarios/lista.html', {
        'ordinario': ordinario,
        'iddocs': iddocs,
        'destinatarios': destinatarios,
        'materia': ordinario.materia,
        'fecha': ordinario.fecha,
        'items_per_page': items_per_page,
    })

@login_required
def ordinarios_anular(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    items_per_page = request.GET.get('items_per_page', '10')
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    total_count = Ordinario.objects.count()
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        messages.error(request, 'El libro está bloqueado. No se pueden anular ni restaurar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if ordinario.autor != request.user.username[:10] and not request.user.is_staff:
        messages.error(request, 'No tienes permiso para anular este ordinario.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    ordinario.anulada = not ordinario.anulada
    ordinario.save()
    
    accion = 'ANULADO' if ordinario.anulada else 'RESTAURADO'
    Auditoria.objects.create(
        usuario=request.user,
        tipo=accion,
        tabla='ordinarios',
        registro_id=pk,
        detalles=f'Ordinario {ordinario.numero} {accion.lower()} por {request.user.username}'
    )
    messages.success(request, f'Ordinario {ordinario.numero} {"anulado" if ordinario.anulada else "restaurado"} correctamente.')
    
    page = get_page_for_ordinario(ordinario, items_per_page, total_count, Ordinario.objects.all().order_by('-numero', '-creada'))
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&page={page}#ordinario-{ordinario.pk}")

@login_required
def ordinarios_eliminar(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    items_per_page = request.GET.get('items_per_page', '10')
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        messages.error(request, 'El libro está bloqueado. No se pueden eliminar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if ordinario.autor != request.user.username[:10]:
        messages.error(request, 'No tienes permiso para eliminar este ordinario.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if request.method == 'POST':
        with transaction.atomic():
            # Eliminar todas las entradas con el mismo número
            Ordinario.objects.filter(numero=ordinario.numero).delete()
            Auditoria.objects.create(
                usuario=request.user,
                tipo='ELIMINAR',
                tabla='ordinarios',
                registro_id=ordinario.numero,
                detalles=f'Eliminado ordinario {ordinario.numero}'
            )
        messages.success(request, f'Ordinario {ordinario.numero} eliminado correctamente.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")