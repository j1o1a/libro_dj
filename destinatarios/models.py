from django.db import models

class Destinatario(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    orden = models.IntegerField(default=0, help_text="Orden de aparición en las listas de selección")
    es_municipio = models.BooleanField(
        default=True,
        help_text="Indica si el destinatario pertenece a 'Dentro del Municipio' (True) o 'Fuera del Municipio' (False)"
    )

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['orden']