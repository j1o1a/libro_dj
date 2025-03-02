from django.db import models
from django.contrib.auth.models import User  # Cambiamos la importación

class Auditoria(models.Model):
    TIPOS = (
        ('CREAR', 'Creación'),
        ('MODIFICAR', 'Modificación'),
        ('ANULAR', 'Anulación'),
        ('ELIMINAR', 'Eliminación'),
        ('RESTAURAR', 'Restauración'),
        ('BLOQUEAR', 'Bloqueo'),
        ('DESBLOQUEAR', 'Desbloqueo'),
    )
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=15, choices=TIPOS)
    tabla = models.CharField(max_length=20)
    registro_id = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.TextField()

    class Meta:
        ordering = ['-fecha']