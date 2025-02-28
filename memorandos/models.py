from django.db import models
from core.models import CustomUser

class Memorando(models.Model):
    numero = models.PositiveIntegerField(verbose_name="# Memorando")
    fecha = models.DateField(verbose_name="Fecha")
    iddoc = models.PositiveIntegerField(verbose_name="IDDOC")
    destinatario = models.CharField(max_length=100, verbose_name="Destinatario")
    materia = models.TextField(max_length=5000, verbose_name="Materia")
    autor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Autor")
    anulado = models.BooleanField(default=False, verbose_name="Anulado")

    class Meta:
        ordering = ['-numero']

    def __str__(self):
        return f"Memorando #{self.numero}"