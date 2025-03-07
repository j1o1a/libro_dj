from django.db import models
from django.contrib.auth.models import User

class Memorando(models.Model):
    numero = models.PositiveIntegerField("Nº Memorando", unique=True)  # Actualmente con unique=True
    fecha = models.DateField("Fecha")
    iddoc = models.PositiveIntegerField("IDDOC", null=True, blank=True)
    destinatario = models.CharField(max_length=100, blank=True)
    materia = models.TextField(max_length=5000)
    autor = models.CharField(max_length=10)
    anulada = models.BooleanField(default=False)
    redom = models.BooleanField(default=False)  # Campo añadido previamente
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-numero']

    def save(self, *args, **kwargs):
        if not self.pk:
            ultimo = Memorando.objects.order_by('-numero').first()
            self.numero = (ultimo.numero + 1) if ultimo else 1
        super().save(*args, **kwargs)

class MemorandoConfig(models.Model):
    bloqueado = models.BooleanField(default=False)
    bloqueado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Configuración del Libro de Memorandos"
        verbose_name_plural = "Configuraciones del Libro de Memorandos"