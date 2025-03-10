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

logger = logging.getLogger(__name__)

DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

def get_page_for_ordinario(ordinario, items_per_page, total_count, ordinarios_list):
    items_per_page_int = int(items_per_page) if items_per_page != 'all' else total_count
    count_before = 0
    for o in ordinarios_list:
        if o.numero > ordinario.numero or (o.numero == ordinario.numero and o.pk > ordinario.pk):
            count_before += 1
    page = (count_before // items_per_page_int) + 1 if count_before > 0 else 1
    return page

def format_fecha(fecha):
    dia_semana = DIAS_SEMANA[fecha.weekday()]
    dia = fecha.day
    mes = MESES[fecha.month - 1]
    año = fecha.year
    return f"{dia_semana} {dia} de {mes} del {año}"

@login_required
def ordinarios_lista(request):
    logger.info(f"Usuario {request.user.username} accedió a la lista de ordinarios")
    items_per_page = request.GET.get('items_per_page', '10')
    page = request.GET.get('page', '1')
    year = request.GET.get('year', datetime.now().year)
    
    try:
        year = int(year)
    except ValueError:
        logger.warning(f"Usuario {request.user.username} ingresó un año inválido: {year}, usando año actual")
        year = datetime.now().year
    
    total_count = Ordinario.objects.filter(fecha__year=year).count()
    if items_per_page == 'all':
        items_per_page_int = total_count
    else:
        try:
            items_per_page_int = int(items_per_page)
        except (ValueError, TypeError):
            logger.warning(f"Usuario {request.user.username} ingresó items_per_page inválido: {items_per_page}, usando 10")
            items_per_page_int = 10
            items_per_page = '10'
    
    all_ordinarios = Ordinario.objects.filter(fecha__year=year).only(
        'pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom'
    ).order_by('-numero', '-creada')
    paginator = Paginator(all_ordinarios, items_per_page_int)
    
    try:
        paginated_ordinarios = paginator.page(page)
    except PageNotAnInteger:
        logger.debug(f"Usuario {request.user.username} solicitó página no numérica: {page}, redirigiendo a página 1")
        paginated_ordinarios = paginator.page(1)
    except EmptyPage:
        logger.debug(f"Usuario {request.user.username} solicitó página vacía: {page}, redirigiendo a última página")
        paginated_ordinarios = paginator.page(paginator.num_pages)
    
    page_obj = paginated_ordinarios
    visible_numbers = list(set(o.numero for o in paginated_ordinarios))
    
    ordinarios_list = list(
        Ordinario.objects.filter(fecha__year=year, numero__in=visible_numbers).only(
            'pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom'
        ).order_by('-numero', '-creada')
    )
    
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
                    'fecha_texto': format_fecha(items_for_numero[0].fecha) if items_for_numero[0].fecha else '',
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
            'fecha_texto': format_fecha(items_for_numero[0].fecha) if items_for_numero[0].fecha else '',
        }
    
    for o in paginated_ordinarios:
        o.es_mas_reciente = (o.pk == latest_entries.get(o.numero))
        o.es_multiple = es_multiple_dict.get(o.numero, False)
        o.is_first_in_group = (o.pk == first_entries.get(o.numero))
        o.is_last_in_group = (o.pk == last_entries.get(o.numero))
    
    edit_data = {}
    for numero in visible_numbers:
        entries = [o for o in ordinarios_list if o.numero == numero]
        unique_destinatarios = [{'destinatario': destinatario} for destinatario in set(o.destinatario for o in entries)]
        edit_data[numero] = unique_destinatarios
        logger.debug(f"Destinatarios para ordinario {numero}: {[d['destinatario'] for d in unique_destinatarios]}")
    
    # Caché para destinatarios
    cache_key_destinatarios = 'destinatarios_ordinarios'
    destinatarios_cached = cache.get(cache_key_destinatarios)
    if destinatarios_cached is None:
        destinatarios_dentro = list(Destinatario.objects.filter(es_municipio=True).order_by('orden'))
        destinatarios_fuera = list(Destinatario.objects.filter(es_municipio=False).order_by('orden'))
        cache.set(cache_key_destinatarios, {'dentro': destinatarios_dentro, 'fuera': destinatarios_fuera}, timeout=3600)
        logger.info(f"Usuario {request.user.username} generó caché de destinatarios")
    else:
        destinatarios_dentro = destinatarios_cached['dentro']
        destinatarios_fuera = destinatarios_cached['fuera']
        logger.debug(f"Usuario {request.user.username} usó caché de destinatarios")
    
    # Caché para años
    cache_key_years = 'ordinarios_years'
    years = cache.get(cache_key_years)
    if years is None:
        years_db = sorted(set(Ordinario.objects.values_list('fecha__year', flat=True)), reverse=True)
        years = years_db
        current_year = datetime.now().year
        if datetime.now().month == 12 and datetime.now().day == 31:
            if current_year + 1 not in years:
                years.insert(0, current_year + 1)
                logger.info(f"Usuario {request.user.username} vio el año siguiente {current_year + 1} en el selector")
        cache.set(cache_key_years, years, timeout=86400)  # Cache por 24 horas
        logger.info(f"Usuario {request.user.username} generó caché de años: {years}")
    else:
        logger.debug(f"Usuario {request.user.username} usó caché de años: {years}")
    
    config, created = LibroConfig.objects.select_related('bloqueado_por').get_or_create(id=1)
    fecha_actual = datetime.now().date()
    fecha_actual_texto = format_fecha(fecha_actual)
    
    logger.info(f"Usuario {request.user.username} cargó lista de ordinarios para año {year} con {total_count} registros")
    return render(request, 'ordinarios/lista.html', {
        'ordinarios': paginated_ordinarios,
        'page_obj': page_obj,
        'items_per_page': str(items_per_page),
        'fecha_actual': fecha_actual.strftime('%Y-%m-%d'),
        'fecha_actual_texto': fecha_actual_texto,
        'destinatarios_dentro': destinatarios_dentro,
        'destinatarios_fuera': destinatarios_fuera,
        'config': config,
        'active_tab': 'ordinarios',
        'grupos_datos': grupos_datos,
        'edit_data': edit_data,
        'total_count': total_count,
        'years': years,
        'selected_year': year,
    })

@login_required
def ordinarios_bloquear(request):
    logger.info(f"Usuario {request.user.username} intentó acceder a bloquear/desbloquear el libro")
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    items_per_page = request.GET.get('items_per_page', '10')
    year = request.GET.get('year', datetime.now().year)
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        logger.warning(f"Usuario {request.user.username} intentó acceder a libro bloqueado por {config.bloqueado_por.username}")
        return render(request, 'ordinarios/lista.html', {
            'ordinarios': Ordinario.objects.filter(fecha__year=year).only('pk', 'numero'),
            'items_per_page': items_per_page,
            'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
            'fecha_actual_texto': format_fecha(datetime.now().date()),
            'destinatarios_dentro': cache.get_or_set('destinatarios_ordinarios_dentro', list(Destinatario.objects.filter(es_municipio=True).order_by('orden')), timeout=3600),
            'destinatarios_fuera': cache.get_or_set('destinatarios_ordinarios_fuera', list(Destinatario.objects.filter(es_municipio=False).order_by('orden')), timeout=3600),
            'config': config,
            'active_tab': 'ordinarios',
            'show_blocked_modal': True,
            'total_count': Ordinario.objects.filter(fecha__year=year).count(),
            'years': sorted(set(Ordinario.objects.values_list('fecha__year', flat=True)), reverse=True),
            'selected_year': int(year),
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
        logger.info(f"Usuario {request.user.username} {accion.lower()} el libro de ordinarios")
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={year}")

@login_required
def ordinarios_agregar(request):
    logger.info(f"Usuario {request.user.username} accedió a agregar un ordinario")
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    items_per_page = request.GET.get('items_per_page', '10')
    total_count = Ordinario.objects.count()
    ordinarios_list = list(Ordinario.objects.only('pk', 'numero', 'creada').order_by('-numero', '-creada'))
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        logger.warning(f"Usuario {request.user.username} intentó agregar ordinario con libro bloqueado por {config.bloqueado_por.username}")
        messages.error(request, 'El libro está bloqueado. No se pueden agregar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if request.method == 'POST':
        data = request.POST
        materia = data.get('materia', '').strip()
        iddoc_input = data.get('iddoc', '').strip()
        logger.info(f"Usuario {request.user.username} envió datos para agregar ordinario: iddoc={iddoc_input}, materia={materia}")
        
        fecha = datetime.now().date()
        
        destinatarios = []
        i = 1
        while True:
            select_key = f'destinatario_select_{i}'
            custom_key = f'destinatario_custom_{i}'
            if select_key not in data:
                break
            select_values = data.getlist(f'destinatario_select_{i}')
            custom_value = data.get(custom_key, '').strip()
            for select_value in select_values:
                select_value = select_value.strip()
                if select_value in ['Otro_Dentro', 'Otro_Fuera']:
                    if not custom_value:
                        logger.warning(f"Usuario {request.user.username} no especificó destinatario personalizado en campo #{i}")
                        messages.error(request, f'Por favor, especifique un destinatario personalizado para el campo #{i}.')
                        return render(request, 'ordinarios/lista.html', {
                            'ordinarios': Ordinario.objects.only('pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom'),
                            'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
                            'fecha_actual_texto': format_fecha(datetime.now().date()),
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
        
        destinatarios = list(dict.fromkeys(destinatarios))
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()] or [None]
        
        try:
            with transaction.atomic():
                ultimo = Ordinario.objects.filter(fecha__year=fecha.year).select_for_update().order_by('-numero').first()
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
                    usuario=request.user,
                    tipo='CREAR',
                    tabla='ordinarios',
                    registro_id=numero,
                    detalles=f'Creado ordinario {numero} con {len(registros)} entradas (IDDOC x Destinatarios)'
                )
                messages.success(request, f'Ordinario {numero} agregado con {len(registros)} entradas.')
                logger.info(f"Usuario {request.user.username} agregó ordinario {numero} con {len(registros)} entradas")
        
        except ValueError as e:
            logger.error(f"Usuario {request.user.username} falló al agregar ordinario: Error en iddoc={iddoc_input}, {str(e)}")
            messages.error(request, f'Error en los datos: {str(e)}. Asegúrate de que "iddoc" sean números válidos separados por comas.')
        
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={fecha.year}")
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
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

logger = logging.getLogger(__name__)

DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

def get_page_for_ordinario(ordinario, items_per_page, total_count, ordinarios_list):
    items_per_page_int = int(items_per_page) if items_per_page != 'all' else total_count
    count_before = 0
    for o in ordinarios_list:
        if o.numero > ordinario.numero or (o.numero == ordinario.numero and o.pk > ordinario.pk):
            count_before += 1
    page = (count_before // items_per_page_int) + 1 if count_before > 0 else 1
    return page

def format_fecha(fecha):
    dia_semana = DIAS_SEMANA[fecha.weekday()]
    dia = fecha.day
    mes = MESES[fecha.month - 1]
    año = fecha.year
    return f"{dia_semana} {dia} de {mes} del {año}"

@login_required
def ordinarios_lista(request):
    logger.info(f"Usuario {request.user.username} accedió a la lista de ordinarios")
    items_per_page = request.GET.get('items_per_page', '10')
    page = request.GET.get('page', '1')
    year = request.GET.get('year', datetime.now().year)
    
    try:
        year = int(year)
    except ValueError:
        logger.warning(f"Usuario {request.user.username} ingresó un año inválido: {year}, usando año actual")
        year = datetime.now().year
    
    total_count = Ordinario.objects.filter(fecha__year=year).count()
    if items_per_page == 'all':
        items_per_page_int = total_count
    else:
        try:
            items_per_page_int = int(items_per_page)
        except (ValueError, TypeError):
            logger.warning(f"Usuario {request.user.username} ingresó items_per_page inválido: {items_per_page}, usando 10")
            items_per_page_int = 10
            items_per_page = '10'
    
    all_ordinarios = Ordinario.objects.filter(fecha__year=year).only(
        'pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom'
    ).order_by('-numero', '-creada')
    paginator = Paginator(all_ordinarios, items_per_page_int)
    
    try:
        paginated_ordinarios = paginator.page(page)
    except PageNotAnInteger:
        logger.debug(f"Usuario {request.user.username} solicitó página no numérica: {page}, redirigiendo a página 1")
        paginated_ordinarios = paginator.page(1)
    except EmptyPage:
        logger.debug(f"Usuario {request.user.username} solicitó página vacía: {page}, redirigiendo a última página")
        paginated_ordinarios = paginator.page(paginator.num_pages)
    
    page_obj = paginated_ordinarios
    visible_numbers = list(set(o.numero for o in paginated_ordinarios))
    
    ordinarios_list = list(
        Ordinario.objects.filter(fecha__year=year, numero__in=visible_numbers).only(
            'pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom'
        ).order_by('-numero', '-creada')
    )
    
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
                    'fecha_texto': format_fecha(items_for_numero[0].fecha) if items_for_numero[0].fecha else '',
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
            'fecha_texto': format_fecha(items_for_numero[0].fecha) if items_for_numero[0].fecha else '',
        }
    
    for o in paginated_ordinarios:
        o.es_mas_reciente = (o.pk == latest_entries.get(o.numero))
        o.es_multiple = es_multiple_dict.get(o.numero, False)
        o.is_first_in_group = (o.pk == first_entries.get(o.numero))
        o.is_last_in_group = (o.pk == last_entries.get(o.numero))
    
    edit_data = {}
    for numero in visible_numbers:
        entries = [o for o in ordinarios_list if o.numero == numero]
        unique_destinatarios = [{'destinatario': destinatario} for destinatario in set(o.destinatario for o in entries)]
        edit_data[numero] = unique_destinatarios
        logger.debug(f"Destinatarios para ordinario {numero}: {[d['destinatario'] for d in unique_destinatarios]}")
    
    # Caché para destinatarios (indefinido)
    cache_key_destinatarios = 'destinatarios_ordinarios'
    destinatarios_cached = cache.get(cache_key_destinatarios)
    if destinatarios_cached is None:
        destinatarios_dentro = list(Destinatario.objects.filter(es_municipio=True).order_by('orden'))
        destinatarios_fuera = list(Destinatario.objects.filter(es_municipio=False).order_by('orden'))
        cache.set(cache_key_destinatarios, {'dentro': destinatarios_dentro, 'fuera': destinatarios_fuera}, timeout=None)
        logger.info(f"Usuario {request.user.username} generó caché indefinido de destinatarios")
    else:
        destinatarios_dentro = destinatarios_cached['dentro']
        destinatarios_fuera = destinatarios_cached['fuera']
        logger.debug(f"Usuario {request.user.username} usó caché de destinatarios")
    
    # Caché para años (24 horas)
    cache_key_years = 'ordinarios_years'
    years = cache.get(cache_key_years)
    if years is None:
        years_db = sorted(set(Ordinario.objects.values_list('fecha__year', flat=True)), reverse=True)
        years = years_db
        current_year = datetime.now().year
        if datetime.now().month == 12 and datetime.now().day == 31:
            if current_year + 1 not in years:
                years.insert(0, current_year + 1)
                logger.info(f"Usuario {request.user.username} vio el año siguiente {current_year + 1} en el selector")
        cache.set(cache_key_years, years, timeout=86400)  # Cache por 24 horas
        logger.info(f"Usuario {request.user.username} generó caché de años: {years}")
    else:
        logger.debug(f"Usuario {request.user.username} usó caché de años: {years}")
    
    config, created = LibroConfig.objects.select_related('bloqueado_por').get_or_create(id=1)
    fecha_actual = datetime.now().date()
    fecha_actual_texto = format_fecha(fecha_actual)
    
    logger.info(f"Usuario {request.user.username} cargó lista de ordinarios para año {year} con {total_count} registros")
    return render(request, 'ordinarios/lista.html', {
        'ordinarios': paginated_ordinarios,
        'page_obj': page_obj,
        'items_per_page': str(items_per_page),
        'fecha_actual': fecha_actual.strftime('%Y-%m-%d'),
        'fecha_actual_texto': fecha_actual_texto,
        'destinatarios_dentro': destinatarios_dentro,
        'destinatarios_fuera': destinatarios_fuera,
        'config': config,
        'active_tab': 'ordinarios',
        'grupos_datos': grupos_datos,
        'edit_data': edit_data,
        'total_count': total_count,
        'years': years,
        'selected_year': year,
    })

@login_required
def ordinarios_agregar(request):
    logger.info(f"Usuario {request.user.username} accedió a agregar un ordinario")
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    items_per_page = request.GET.get('items_per_page', '10')
    total_count = Ordinario.objects.count()
    ordinarios_list = list(Ordinario.objects.only('pk', 'numero', 'creada').order_by('-numero', '-creada'))
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        logger.warning(f"Usuario {request.user.username} intentó agregar ordinario con libro bloqueado por {config.bloqueado_por.username}")
        messages.error(request, 'El libro está bloqueado. No se pueden agregar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if request.method == 'POST':
        data = request.POST
        materia = data.get('materia', '').strip()
        iddoc_input = data.get('iddoc', '').strip()
        logger.info(f"Usuario {request.user.username} envió datos para agregar ordinario: iddoc={iddoc_input}, materia={materia}")
        
        fecha = datetime.now().date()
        
        destinatarios = []
        i = 1
        while True:
            select_key = f'destinatario_select_{i}'
            custom_key = f'destinatario_custom_{i}'
            if select_key not in data:
                break
            select_values = data.getlist(f'destinatario_select_{i}')
            custom_value = data.get(custom_key, '').strip()
            for select_value in select_values:
                select_value = select_value.strip()
                if select_value in ['Otro_Dentro', 'Otro_Fuera']:
                    if not custom_value:
                        logger.warning(f"Usuario {request.user.username} no especificó destinatario personalizado en campo #{i}")
                        messages.error(request, f'Por favor, especifique un destinatario personalizado para el campo #{i}.')
                        return render(request, 'ordinarios/lista.html', {
                            'ordinarios': Ordinario.objects.only('pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom'),
                            'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
                            'fecha_actual_texto': format_fecha(datetime.now().date()),
                            'destinatarios_dentro': cache.get('destinatarios_ordinarios', {}).get('dentro', []),
                            'destinatarios_fuera': cache.get('destinatarios_ordinarios', {}).get('fuera', []),
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
        
        destinatarios = list(dict.fromkeys(destinatarios))
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()] or [None]
        
        try:
            with transaction.atomic():
                ultimo = Ordinario.objects.filter(fecha__year=fecha.year).select_for_update().order_by('-numero').first()
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
                
                # Invalidar caché de años si el año es nuevo
                years_cached = cache.get('ordinarios_years') or []
                if fecha.year not in years_cached:
                    cache.delete('ordinarios_years')
                    logger.info(f"Usuario {request.user.username} invalidó caché de años al agregar ordinario en {fecha.year}")
                
                Auditoria.objects.create(
                    usuario=request.user,
                    tipo='CREAR',
                    tabla='ordinarios',
                    registro_id=numero,
                    detalles=f'Creado ordinario {numero} con {len(registros)} entradas (IDDOC x Destinatarios)'
                )
                messages.success(request, f'Ordinario {numero} agregado con {len(registros)} entradas.')
                logger.info(f"Usuario {request.user.username} agregó ordinario {numero} con {len(registros)} entradas")
        
        except ValueError as e:
            logger.error(f"Usuario {request.user.username} falló al agregar ordinario: Error en iddoc={iddoc_input}, {str(e)}")
            messages.error(request, f'Error en los datos: {str(e)}. Asegúrate de que "iddoc" sean números válidos separados por comas.')
        
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={fecha.year}")
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")

@login_required
def ordinarios_editar(request, pk):
    logger.info(f"Usuario {request.user.username} intentó editar ordinario con pk={pk}")
    ordinario = get_object_or_404(Ordinario, pk=pk)
    items_per_page = request.GET.get('items_per_page', '10')
    page = request.GET.get('page', '1')
    year = request.GET.get('year', datetime.now().year)
    grupo_ordinarios = Ordinario.objects.filter(numero=ordinario.numero).order_by('-creada')
    
    if request.method == 'POST':
        data = request.POST
        logger.debug(f"Datos recibidos del formulario: {data}")
        
        fecha = ordinario.fecha  # Mantener la fecha original
        iddoc_input = data.get('iddoc', '').strip()
        materia = data.get('materia', '').strip()
        logger.info(f"Usuario {request.user.username} editando ordinario {ordinario.numero}: iddoc={iddoc_input}, materia={materia}")
        
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()] or [None]
        iddoc_list = list(dict.fromkeys([int(idd.replace('.', '')) if idd else None for idd in iddoc_list]))
        
        destinatarios = []
        for key in data.keys():
            if key.startswith('destinatario_select_'):
                index = int(key.split('_')[-1])
                select_values = data.getlist(key)
                custom_value = data.get(f'destinatario_custom_{index}', '').strip()
                logger.debug(f"Procesando {key}: select_values={select_values}, custom_value={custom_value}")
                for select_value in select_values:
                    select_value = select_value.strip()
                    if select_value in ['Otro_Dentro', 'Otro_Fuera'] and custom_value:
                        destinatarios.append(custom_value)
                    elif select_value:
                        destinatarios.append(select_value)
        
        logger.debug(f"Destinatarios procesados antes de validación: {destinatarios}")
        
        total_count = Ordinario.objects.filter(fecha__year=year).count()
        ordinarios_list = list(
            Ordinario.objects.filter(fecha__year=year).only('pk', 'numero', 'iddoc', 'destinatario', 'materia', 'fecha', 'creada', 'autor', 'anulada', 'redom')
            .order_by('-numero', '-creada')
        )
        
        if not destinatarios:
            logger.warning(f"Usuario {request.user.username} intentó editar ordinario {ordinario.numero} sin destinatarios")
            messages.error(request, 'Debe especificar al menos un destinatario.')
            form_data = {
                'fecha': fecha.strftime('%Y-%m-%d'),
                'iddoc': ", ".join(str(idd) for idd in iddoc_list if idd is not None),
                'materia': materia,
                'destinatarios': [{'select_value': d, 'custom_value': ''} for d in set(destinatarios) if d] if destinatarios else [],
            }
            paginator = Paginator(ordinarios_list, int(items_per_page) if items_per_page != 'all' else total_count)
            try:
                paginated_ordinarios = paginator.page(page)
            except PageNotAnInteger:
                paginated_ordinarios = paginator.page(1)
            except EmptyPage:
                paginated_ordinarios = paginator.page(paginator.num_pages)
            
            page_obj = paginated_ordinarios
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
                            'fecha_texto': format_fecha(items_for_numero[0].fecha) if items_for_numero[0].fecha else '',
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
                    'fecha_texto': format_fecha(items_for_numero[0].fecha) if items_for_numero[0].fecha else '',
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
            fecha_actual_texto = format_fecha(datetime.now().date())
            
            return render(request, 'ordinarios/lista.html', {
                'ordinarios': paginated_ordinarios,
                'page_obj': page_obj,
                'items_per_page': items_per_page,
                'fecha_actual': fecha_actual,
                'fecha_actual_texto': fecha_actual_texto,
                'destinatarios_dentro': destinatarios_dentro,
                'destinatarios_fuera': destinatarios_fuera,
                'config': config,
                'active_tab': 'ordinarios',
                'grupos_datos': grupos_datos,
                'edit_data': edit_data,
                'total_count': total_count,
                'form_data': form_data,
                'show_edit_modal': ordinario.numero,
                'years': sorted(set(Ordinario.objects.values_list('fecha__year', flat=True)), reverse=True),
                'selected_year': int(year),
            })
        
        destinatarios = list(dict.fromkeys(destinatarios))
        
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
            grupo_ordinarios.delete()
            Ordinario.objects.bulk_create(registros)
        
        messages.success(request, f'Ordinario {ordinario.numero} editado correctamente.')
        logger.info(f"Usuario {request.user.username} editó ordinario {ordinario.numero} con {len(registros)} entradas")
        page = get_page_for_ordinario(ordinario, items_per_page, total_count, ordinarios_list)
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&page={page}&year={year}#ordinario-{ordinario.pk}")
    
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
        'years': sorted(set(Ordinario.objects.values_list('fecha__year', flat=True)), reverse=True),
        'selected_year': int(year),
    })

@login_required
def ordinarios_anular(request, pk):
    logger.info(f"Usuario {request.user.username} intentó anular ordinario con pk={pk}")
    ordinario = get_object_or_404(Ordinario, pk=pk)
    items_per_page = request.GET.get('items_per_page', '10')
    year = request.GET.get('year', datetime.now().year)
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    total_count = Ordinario.objects.filter(fecha__year=year).count()
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        logger.warning(f"Usuario {request.user.username} intentó anular ordinario {ordinario.numero} con libro bloqueado por {config.bloqueado_por.username}")
        messages.error(request, 'El libro está bloqueado. No se pueden anular ni restaurar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={year}")
    
    if ordinario.autor != request.user.username[:10] and not request.user.is_staff:
        logger.warning(f"Usuario {request.user.username} intentó anular ordinario {ordinario.numero} sin permiso")
        messages.error(request, 'No tienes permiso para anular este ordinario.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={year}")
    
    grupo_ordinarios = Ordinario.objects.filter(numero=ordinario.numero)
    nuevo_estado = not ordinario.anulada
    
    with transaction.atomic():
        grupo_ordinarios.update(anulada=nuevo_estado)
    
    accion = 'ANULADO' if nuevo_estado else 'RESTAURADO'
    Auditoria.objects.create(
        usuario=request.user,
        tipo=accion,
        tabla='ordinarios',
        registro_id=ordinario.numero,
        detalles=f'Ordinario {ordinario.numero} {accion.lower()} por {request.user.username}'
    )
    messages.success(request, f'Ordinario {ordinario.numero} {"anulado" if nuevo_estado else "restaurado"} correctamente.')
    logger.info(f"Usuario {request.user.username} {accion.lower()} ordinario {ordinario.numero}")
    
    page = get_page_for_ordinario(ordinario, items_per_page, total_count, Ordinario.objects.filter(fecha__year=year).order_by('-numero', '-creada'))
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&page={page}&year={year}#ordinario-{ordinario.pk}")

@login_required
def ordinarios_eliminar(request, pk):
    logger.info(f"Usuario {request.user.username} intentó eliminar ordinario con pk={pk}")
    ordinario = get_object_or_404(Ordinario, pk=pk)
    items_per_page = request.GET.get('items_per_page', '10')
    year = request.GET.get('year', datetime.now().year)
    config = LibroConfig.objects.select_related('bloqueado_por').get(id=1)
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        logger.warning(f"Usuario {request.user.username} intentó eliminar ordinario {ordinario.numero} con libro bloqueado por {config.bloqueado_por.username}")
        messages.error(request, 'El libro está bloqueado. No se pueden eliminar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={year}")
    
    if ordinario.autor != request.user.username[:10]:
        logger.warning(f"Usuario {request.user.username} intentó eliminar ordinario {ordinario.numero} sin permiso")
        messages.error(request, 'No tienes permiso para eliminar este ordinario.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={year}")
    
    if request.method == 'POST':
        with transaction.atomic():
            Ordinario.objects.filter(numero=ordinario.numero).delete()
            Auditoria.objects.create(
                usuario=request.user,
                tipo='ELIMINAR',
                tabla='ordinarios',
                registro_id=ordinario.numero,
                detalles=f'Eliminado ordinario {ordinario.numero}'
            )
        messages.success(request, f'Ordinario {ordinario.numero} eliminado correctamente.')
        logger.info(f"Usuario {request.user.username} eliminó ordinario {ordinario.numero}")
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={year}")
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&year={year}")