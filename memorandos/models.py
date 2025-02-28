from django.db import models
from django.contrib.auth.models import User

class Memorando(models.Model):
    numero = models.PositiveIntegerField("Nº Ordinario", unique=True)
    fecha = models.DateField("Fecha")
    iddoc = models.PositiveIntegerField("IDDOC")
    destinatario = models.CharField(max_length=100, blank=True)
    materia = models.TextField(max_length=5000)
    autor = models.CharField(max_length=10)  # Iniciales del usuario
    anulada = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-numero']

    def save(self, *args, **kwargs):
        if not self.pk:  # Si es nueva entrada
            ultimo = Ordinario.objects.order_by('-numero').first()
            self.numero = (ultimo.numero + 1) if ultimo else 1
        super().save(*args, **kwargs)