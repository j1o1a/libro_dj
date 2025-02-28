from django.db import models

class Destinatario(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['nombre']