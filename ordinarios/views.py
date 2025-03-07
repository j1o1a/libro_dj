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

# Función auxiliar para calcular la página de un ordinario
def get_page_for_ordinario(ordinario, items_per_page):
    ordinarios_list = Ordinario.objects.all().order_by('-numero')
    items_per_page_int = ordinarios_list.count() if items_per_page == 'all' else int(items_per_page)
    paginator = Paginator(ordinarios_list, items_per_page_int)
    position = next(i + 1 for i, o in enumerate(ordinarios_list) if o.pk == ordinario.pk)
    page = (position - 1) // items_per_page_int + 1 if position > 0 else 1
    return page

@login_required
def ordinarios_lista(request):
    items_per_page = request.GET.get('items_per_page', '10')
    ordinarios_list = Ordinario.objects.all().order_by('-numero')
    
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
    })

@login_required
def ordinarios_agregar(request):
    config = LibroConfig.objects.get(id=1)
    items_per_page = request.GET.get('items_per_page', '10')
    
    # Verificar si el libro está bloqueado y el usuario no es el que lo bloqueó ni staff
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        messages.error(request, 'El libro está bloqueado. No se pueden agregar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if request.method == 'POST':
        data = request.POST
        fecha = data.get('fecha') or datetime.now().date()
        destinatario_select = data.get('destinatario_select')
        destinatario_custom = data.get('destinatario_custom', '').strip()
        materia = data.get('materia', '').strip()
        iddoc_input = data.get('iddoc', '').strip()
        
        if destinatario_select in ['Otro_Dentro', 'Otro_Fuera']:
            if not destinatario_custom:
                messages.error(request, 'Por favor, especifique un destinatario personalizado.')
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
            destinatario = destinatario_custom
            es_municipio = True if destinatario_select == 'Otro_Dentro' else False
        else:
            destinatario = destinatario_select
            es_municipio = Destinatario.objects.get(nombre=destinatario).es_municipio
        
        iddoc_list = [idd.strip() for idd in iddoc_input.split(',') if idd.strip()]
        
        try:
            with transaction.atomic():
                ultimo = Ordinario.objects.order_by('-numero').first()
                numero = (ultimo.numero + 1) if ultimo else 1
                
                registros = []
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
        
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")

@login_required
def ordinarios_editar(request, pk):
    ordinario = get_object_or_404(Ordinario, pk=pk)
    items_per_page = request.GET.get('items_per_page', '10')
    config = LibroConfig.objects.get(id=1)
    
    if config.bloqueado and config.bloqueado_por != request.user and not request.user.is_staff:
        messages.error(request, 'El libro está bloqueado. No se pueden editar registros.')
        return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")
    
    if request.method == 'POST':
        data = request.POST
        fecha = data.get('fecha')
        iddoc = data.get('iddoc', '').strip()
        destinatario = data.get('destinatario', '').strip()
        materia = data.get('materia', '').strip()
        
        try:
            ordinario.fecha = fecha
            if iddoc:
                ordinario.iddoc = int(iddoc.replace('.', '')) if iddoc else None
            else:
                ordinario.iddoc = None
            ordinario.destinatario = destinatario
            ordinario.materia = materia
            
            ordinario.save()
            
            Auditoria.objects.create(
                usuario=request.user,
                tipo='EDITAR',
                tabla='ordinarios',
                registro_id=pk,
                detalles=f'Ordinario {ordinario.numero} editado por {request.user.username}'
            )
            messages.success(request, f'Ordinario {ordinario.numero} editado correctamente.')
            
            page = get_page_for_ordinario(ordinario, items_per_page)
            return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}&page={page}#ordinario-{ordinario.pk}")
        
        except ValueError as e:
            messages.error(request, f'Error en los datos: {str(e)}. Asegúrate de que "iddoc" sea un número válido.')
    
    return redirect(f"{reverse('ordinarios_lista')}?items_per_page={items_per_page}")

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
    
    # Verificar si el libro está bloqueado y el usuario no es el que lo bloqueó ni staff
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