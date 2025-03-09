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
    ordinarios_list = Ordinario.objects.all().order_by('-numero', '-creada')  # Orden consistente
    items_per_page_int = ordinarios_list.count() if items_per_page == 'all' else int(items_per_page)
    paginator = Paginator(ordinarios_list, items_per_page_int)
    position = next(i + 1 for i, o in enumerate(ordinarios_list) if o.pk == ordinario.pk)
    page = (position - 1) // items_per_page_int + 1 if position > 0 else 1
    return page

@login_required
def ordinarios_lista(request):
    items_per_page = request.GET.get('items_per_page', '10')
    ordinarios_list = Ordinario.objects.all().order_by('-numero', '-creada')
    
    # Contar registros por número para determinar entradas múltiples
    conteo_por_numero = Counter(o.numero for o in ordinarios_list)
    
    # Identificar la entrada más reciente de cada grupo y preparar datos combinados
    grupos = {}
    grupos_datos = {}
    for o in ordinarios_list:
        if o.numero not in grupos:
            grupos[o.numero] = o  # Entrada más reciente
            grupos_datos[o.numero] = {
                'iddocs': ", ".join(str(ord.iddoc) for ord in Ordinario.objects.filter(numero=o.numero) if ord.iddoc),
                'destinatarios': ", ".join(ord.destinatario for ord in Ordinario.objects.filter(numero=o.numero)),
                'materia': o.materia,
                'fecha': o.fecha.strftime('%Y-%m-%d'),
            }
    
    # Añadir atributos es_mas_reciente y es_multiple
    for o in ordinarios_list:
        o.es_mas_reciente = (o == grupos[o.numero])
        o.es_multiple = conteo_por_numero[o.numero] > 1
    
    # Paginación
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
        page = request.GET.get('page', 1)
        
        try:
            paginated_ordinarios = paginator.page(page)
        except PageNotAnInteger:
            paginated_ordinarios = paginator.page(1)
        except EmptyPage:
            paginated_ordinarios = paginator.page(paginator.num_pages)
        
        page_obj = paginated_ordinarios
    
    # Datos adicionales para el contexto
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
        'grupos_datos': grupos_datos,  # Datos combinados para los modales de edición
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
        
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()] or [None]  # Si no hay iddoc, usar None
        
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
        
        # Dividir iddoc en una lista, manejando el caso vacío
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()] or [None]
        
        # Obtener destinatarios del formulario
        destinatarios = []
        for i in range(1, len(grupo_ordinarios) + 1):  # Máximo basado en registros existentes
            select_key = f'destinatario_select_{i}'
            custom_key = f'destinatario_custom_{i}'
            select_value = data.get(select_key)
            custom_value = data.get(custom_key, '').strip()
            if select_value and select_value in ['Otro_Dentro', 'Otro_Fuera'] and custom_value:
                destinatarios.append(custom_value)
            elif select_value and select_value not in ['Otro_Dentro', 'Otro_Fuera']:
                destinatarios.append(select_value)
            if not select_value:  # Si no hay más destinatarios enviados, paramos
                break
        
        # Actualizar o eliminar registros según los datos enviados
        with transaction.atomic():
            # Si solo hay un iddoc y un destinatario
            if len(iddoc_list) == 1 and len(destinatarios) == 1:
                # Actualizar el primer registro y eliminar los demás
                o = grupo_ordinarios[0]
                o.fecha = fecha
                o.iddoc = iddoc_list[0]
                o.destinatario = destinatarios[0]
                o.materia = materia
                o.save()
                # Eliminar registros sobrantes
                grupo_ordinarios.exclude(pk=o.pk).delete()
            else:
                # Actualizar todos los registros existentes o crear nuevos si faltan
                for i, o in enumerate(grupo_ordinarios):
                    if i < len(iddoc_list) and i < len(destinatarios):
                        o.fecha = fecha
                        o.iddoc = iddoc_list[i]
                        o.destinatario = destinatarios[i]
                        o.materia = materia
                        o.save()
                    else:
                        o.delete()  # Eliminar registros sobrantes si hay menos datos
                # Crear nuevos registros si hay más datos que registros existentes
                for i in range(len(grupo_ordinarios), min(len(iddoc_list), len(destinatarios))):
                    Ordinario.objects.create(
                        numero=ordinario.numero,
                        fecha=fecha,
                        iddoc=iddoc_list[i] if i < len(iddoc_list) else None,
                        destinatario=destinatarios[i],
                        materia=materia,
                        autor=ordinario.autor,
                        creada=ordinario.creada  # Mantener la fecha original si es necesario
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
