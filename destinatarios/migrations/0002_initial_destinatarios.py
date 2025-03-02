from django.db import migrations

def populate_destinatarios(apps, schema_editor):
    Destinatario = apps.get_model('destinatarios', 'Destinatario')
    destinatarios_iniciales = [
        "Alcalde",
        "SEMU",
        "SECPLAC",
        "DIDECOSO",
        "DAF",
        "Control",
        "Comunicaciones",
        "DOM",
        "DAO",
        "Dirección de TI",
        "Tránsito",
        "DIPROCIG",
        "SS.GG",
        "Sostenibilidad",
        "1.er JPL",
        "2.° JPL",
        "3.er JPL",
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
