from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from .models import Ordinario
from .forms import OrdinarioForm
from auditoria.models import Auditoria

class OrdinarioListView(LoginRequiredMixin, ListView):
    model = Ordinario
    template_name = 'ordinarios/lista.html'
    context_object_name = 'object_list'
    paginate_by = 10

    def get_queryset(self):
        mostrar = self.request.GET.get('mostrar', '10')
        if mostrar == 'Todos':
            return Ordinario.objects.all().order_by('-numero')
        return Ordinario.objects.all().order_by('-numero')[:int(mostrar)]

class OrdinarioCreateView(LoginRequiredMixin, CreateView):
    model = Ordinario
    form_class = OrdinarioForm
    template_name = 'ordinarios/form.html'
    success_url = reverse_lazy('ordinarios:lista')

    def form_valid(self, form):
        # Calcular el número correlativo
        ultimo_ordinario = Ordinario.objects.order_by('-numero').first()
        form.instance.numero = (ultimo_ordinario.numero + 1) if ultimo_ordinario else 1
        form.instance.autor = self.request.user
        
        # Guardar el objeto
        response = super().form_valid(form)
        
        # Registrar en auditoría
        Auditoria.objects.create(
            accion="Creado", usuario=self.request.user,
            registro_tipo="Ordinario", registro_id=form.instance.id
        )
        