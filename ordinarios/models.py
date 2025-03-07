from django.db import models
from django.contrib.auth.models import User

class Ordinario(models.Model):
    numero = models.PositiveIntegerField("Nº Ordinario")
    fecha = models.DateField("Fecha")
    iddoc = models.PositiveIntegerField("IDDOC", null=True, blank=True)
    destinatario = models.CharField(max_length=100, blank=True)
    materia = models.TextField(max_length=5000)
    autor = models.CharField(max_length=10)
    anulada = models.BooleanField(default=False)
    redom = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-numero']

    # Sin lógica de numero en save(), se maneja en la vista
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class LibroConfig(models.Model):
    bloqueado = models.BooleanField(default=False)
    bloqueado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Configuración del Libro"
        verbose_name_plural = "Configuraciones del Libro"