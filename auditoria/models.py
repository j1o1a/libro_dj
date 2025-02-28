from django.db import models
from core.models import CustomUser

class Auditoria(models.Model):
    accion = models.CharField(max_length=50)  # Ej: "Creado", "Modificado", "Anulado"
    usuario = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    registro_tipo = models.CharField(max_length=20)  # "Ordinario" o "Memorando"
    registro_id = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.accion} - {self.registro_tipo} #{self.registro_id}"