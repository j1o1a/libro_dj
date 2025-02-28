from django.db import models
from django.conf import settings

class Auditoria(models.Model):
    TIPOS = (
        ('CREAR', 'Creación'),
        ('MODIFICAR', 'Modificación'),
        ('ANULAR', 'Anulación'),
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    tabla = models.CharField(max_length=20)  # "ordinarios" o "memorandos"
    registro_id = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.TextField()

    class Meta:
        ordering = ['-fecha']