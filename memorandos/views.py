from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from .models import Memorando
from .forms import MemorandoForm
from auditoria.models import Auditoria

class MemorandoListView(LoginRequiredMixin, ListView):
    model = Memorando
    template_name = 'memorandos/lista.html'
    context_object_name = 'object_list'
    paginate_by = 10

    def get_queryset(self):
        mostrar = self.request.GET.get('mostrar', '10')
        if mostrar == 'Todos':
            return Memorando.objects.all().order_by('-numero')
        return Memorando.objects.all().order_by('-numero')[:int(mostrar)]

class MemorandoCreateView(LoginRequiredMixin, CreateView):
    model = Memorando
    form_class = MemorandoForm
    template_name = 'memorandos/form.html'
    success_url = reverse_lazy('memorandos:lista')

    def form_valid(self, form):
        # Calcular el número correlativo
        ultimo_memorando = Memorando.objects.order_by('-numero').first()
        form.instance.numero = (ultimo_memorando.numero + 1) if ultimo_memorando else 1
        form.instance.autor = self.request.user
        
        # Guardar el objeto
        response = super().form_valid(form)
        
        # Registrar en auditoría
        Auditoria.objects.create(
            accion="Creado", usuario=self.request.user,
            registro_tipo="Memorando", registro_id=form.instance.id
        )
        
        # Retornar JSON para el modal si es una solicitud AJAX
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'numero': form.instance.numero,
            })
        return response