from django.db import migrations

def populate_destinatarios(apps, schema_editor):
    Destinatario = apps.get_model('destinatarios', 'Destinatario')
    destinatarios_iniciales = [
        "Alcalde",
        "Secretaría Municipal",
        "Secretaría Comunal de Planificación",
        "Dirección de Desarrollo Comunitario y Social",
        "Dirección de Administración y Finanzas",
        "Dirección de Control",
        "Dirección de Comunicaciones",
        "Dirección de Obras Municipales",
        "Dirección de Medio Ambiente, Aseo, Ornato y Operaciones",
        "Dirección de Tecnologías de la Información",
        "Dirección de Tránsito y Transporte Público",
        "Dirección de Seguridad Ciudadana, Fiscalización, Emergencia Comunal",
        "Dirección de Servicios Generales",
        "Dirección de Sostenibilidad",
        "1.er Juzgado de Policía Local",
        "2.° Juzgado de Policía Local",
        "3.er Juzgado de Policía Local",  # Corregido "Loca" a "Local"
    ]
    for nombre in destinatarios_iniciales:
        Destinatario.objects.create(nombre=nombre)

def reverse_populate_destinatarios(apps, schema_editor):
    Destinatario = apps.get_model('destinatarios', 'Destinatario')
    Destinatario.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('destinatarios', '0001_initial'),  # Ajusta si el número de la migración inicial es diferente
    ]

    operations = [
        migrations.RunPython(populate_destinatarios, reverse_populate_destinatarios),
    ]