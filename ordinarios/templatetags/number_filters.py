from django import template

register = template.Library()

@register.filter
def format_thousands(value):
    try:
        num = int(value)
        return "{:,}".format(num).replace(',', '.')
    except (ValueError, TypeError):
        return value

@register.filter
def lookup(value, key):
    return value.get(key) if value else ''

@register.filter
def filter_by_numero(queryset, numero):
    return [o for o in queryset if o.numero == numero]