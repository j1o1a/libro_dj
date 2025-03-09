from django import template

register = template.Library()

@register.filter
def format_thousands(value):
    """
    Formatea un número con puntos como separadores de miles.
    Ejemplo: 1234567 → 1.234.567
    """
    try:
        # Convertir el valor a entero si no lo es
        num = int(value)
        # Formatear con puntos como separadores de miles
        return "{:,}".format(num).replace(',', '.')
    except (ValueError, TypeError):
        return value  # Devolver el valor original si no se puede formatear

@register.filter
def lookup(value, key):
    """
    Permite acceder a un valor en un diccionario usando una clave.
    Ejemplo: {{ grupos_datos|lookup:o.numero|lookup:'iddocs' }}
    """
    return value.get(key) if value else ''