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
from collections import Counter

# Función auxiliar para calcular la página de un ordinario
def get_page_for_ordinario(ordinario, items_per_page):
    ordinarios_list = Ordinario.objects.all().order_by('-numero', '-creada')
    items_per_page_int = ordinarios_list.count() if items_per_page == 'all' else int(items_per_page)
    paginator = Paginator(ordinarios_list, items_per_page_int)
    position = next(i + 1 for i, o in enumerate(ordinarios_list) if o.pk == ordinario.pk)
    page = (position - 1) // items_per_page_int + 1 if position > 0 else 1
    return page

@login_required
def ordinarios_lista(request):
    items_per_page = request.GET.get('items_per_page', '10')
    ordinarios_list = Ordinario.objects.all().order_by('-numero', '-creada')
    
    conteo_por_numero = Counter(o.numero for o in ordinarios_list)
    grupos = {}
    grupos_datos = {}
    for o in ordinarios_list:
        if o.numero not in grupos:
            grupos[o.numero] = o
            grupos_datos[o.numero] = {
                'iddocs': ", ".join(str(ord.iddoc) for ord in Ordinario.objects.filter(numero=o.numero) if ord.iddoc),
                'destinatarios': ", ".join(ord.destinatario for ord in Ordinario.objects.filter(numero=o.numero)),
                'materia': o.materia,
                'fecha': o.fecha.strftime('%Y-%m-%d'),
            }
    
    previous_numero = None
    next_ordinarios = list(ordinarios_list)[1:] + [None]
    for i, o in enumerate(ordinarios_list):
        o.es_mas_reciente = (o == grupos[o.numero])
        o.es_multiple = conteo_por_numero[o.numero] > 1
        o.is_first_in_group = (i == 0) or (previous_numero != o.numero)
        o.is_last_in_group = (next_ordinarios[i] is None) or (next_ordinarios[i].numero != o.numero)
        print(f"Numero={o.numero}, es_multiple={o.es_multiple}, first={o.is_first_in_group}, last={o.is_last_in_group}")  # Debug
        previous_numero = o.numero
    
    # Paginación (sin cambios)
    if items_per_page == 'all':
        paginated_ordinarios = ordinarios_list
        page_obj = None
    else:
        try:
            items_per_page_int = int(items_per_page)
        except (ValueError, TypeError):
            items_per_page_int = 10
            items_per_page = '10'
        
        paginator = Paginator(ordinarios_list, items_per_page_int)
        page = request.GET.get('page', '1')
        
        try:
            paginated_ordinarios = paginator.page(page)
        except PageNotAnInteger:
            paginated_ordinarios = paginator.page(1)
        except EmptyPage:
            paginated_ordinarios = paginator.page(paginator.num_pages)
        
        page_obj = paginated_ordinarios
    
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    destinatarios_dentro = Destinatario.objects.filter(es_municipio=True).order_by('orden')
    destinatarios_fuera = Destinatario.objects.filter(es_municipio=False).order_by('orden')
    config, created = LibroConfig.objects.get_or_create(id=1)
    
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
    })

@login_required
def ordinarios_agregar(request):
    config = LibroConfig.objects.get(id=1)
    items_per_page = request.GET.get('items_per_page', '10')
    
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
            select_value = data.get(select_key)
            custom_value = data.get(custom_key, '').strip()
            if select_value in ['Otro_Dentro', 'Otro_Fuera']:
                if not custom_value:
                    messages.error(request, f'Por favor, especifique un destinatario personalizado para el campo #{i}.')
                    return render(request, 'ordinarios/lista.html', {
                        'ordinarios': Ordinario.objects.all(),
                        'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
                        'destinatarios_dentro': Destinatario.objects.filter(es_municipio=True).order_by('orden'),
                        'destinatarios_fuera': Destinatario.objects.filter(es_municipio=False).order_by('orden'),
                        'config': config,
                        'active_tab': 'ordinarios',
                        'form_data': data,
                        'items_per_page': items_per_page,
                    })
                destinatarios.append(custom_value)
            else:
                destinatarios.append(select_value)
            i += 1
        
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
    grupo_ordinarios = Ordinario.objects.filter(numero=ordinario.numero).order_by('-creada')
    
    if request.method == 'POST':
        data = request.POST
        fecha = data.get('fecha')
        iddoc_input = data.get('iddoc', '').strip()
        materia = data.get('materia', '').strip()
        
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()] or [None]
        
        destinatarios = []
        i = 1
        while f'destinatario_select_{i}' in data:
            select_value = data.get(f'destinatario_select_{i}', '').strip()
            custom_value = data.get(f'destinatario_custom_{i}', '').strip()
            if select_value in ['Otro_Dentro', 'Otro_Fuera'] and custom_value:
                destinatarios.append(custom_value)
            elif select_value:
                destinatarios.append(select_value)
            i += 1
        if not destinatarios:
            destinatarios = [ordinario.destinatario]
        
        with transaction.atomic():
            grupo_ordinarios.delete()
            for i in range(max(len(iddoc_list), len(destinatarios))):
                iddoc = iddoc_list[i] if i < len(iddoc_list) else iddoc_list[-1] if iddoc_list else None
                destinatario = destinatarios[i] if i < len(destinatarios) else destinatarios[-1]
                Ordinario.objects.create(
                    numero=ordinario.numero,
                    fecha=fecha,
                    iddoc=iddoc,
                    destinatario=destinatario,
                    materia=materia,
                    autor=ordinario.autor,
                    creada=ordinario.creada
                )
        
        messages.success(request, f'Ordinario {ordinario.numero} editado correctamente.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    iddocs = ", ".join(str(o.iddoc) for o in grupo_ordinarios if o.iddoc)
    destinatarios = ", ".join(o.destinatario for o in grupo_ordinarios)
    return render(request, 'ordinarios/editar.html', {
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
    config = LibroConfig.objects.get(id=1)
    
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
    
    page = get_page_for_ordinario(ordinario, items_per_page)
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&page={page}#ordinario-{ordinario.pk}")

@login_required
def ordinarios_eliminar(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    items_per_page = request.GET.get('items_per_page', '10')
    config = LibroConfig.objects.get(id=1)
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        messages.error(request, 'El libro está bloqueado. No se pueden eliminar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if ordinario.autor != request.user.username[:10] or ordinario != Ordinario.objects.order_by('-numero').first():
        messages.error(request, 'No tienes permiso para eliminar este ordinario.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if request.method == 'POST':
        numero = ordinario.numero
        ordinario.delete()
        
        Auditoria.objects.create(
            usuario=request.user,
            tipo='ELIMINAR',
            tabla='ordinarios',
            registro_id=pk,
            detalles=f'Ordinario {numero} eliminado por {request.user.username}'
        )
        messages.success(request, f'Ordinario {numero} eliminado correctamente.')
        
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")

@login_required
def ordinarios_bloquear(request):
    config = LibroConfig.objects.get(id=1)
    items_per_page = request.GET.get('items_per_page', '10')
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        return render(request, 'ordinarios/lista.html', {
            'ordinarios': Ordinario.objects.all(),
            'items_per_page': items_per_page,
            'fecha_actual': datetime.now().strftime('%Y-%m-%d'),
            'destinatarios_dentro': Destinatario.objects.filter(es_municipio=True).order_by('orden'),
            'destinatarios_fuera': Destinatario.objects.filter(es_municipio=False).order_by('orden'),
            'config': config,
            'active_tab': 'ordinarios',
            'show_blocked_modal': True
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