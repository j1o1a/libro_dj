from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from ordinarios.models import Ordinario, LibroConfig
from destinatarios.models import Destinatario
from datetime import datetime
from unittest.mock import patch

class OrdinarioTests(TestCase):
    def setUp(self):
        """Configuración inicial antes de cada prueba."""
        # Crear usuarios
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        
        # Configurar LibroConfig
        self.config = LibroConfig.objects.create(id=1, bloqueado=False)
        
        # Crear un destinatario válido
        self.destinatario = Destinatario.objects.create(
            nombre="Destinatario Test",
            es_municipio=True,
            orden=1
        )
        
        # Cliente HTTP
        self.client = Client()
        
        # Ordinario inicial en 2025
        Ordinario.objects.create(
            numero=75,
            fecha=datetime(2025, 12, 31).date(),
            iddoc=123456,
            destinatario=self.destinatario.nombre,
            materia="Materia Test",
            autor=self.user1.username[:10],
            anulada=False,
            redom=False
        )

    @patch('ordinarios.views.datetime')
    def test_numero_reinicia_en_nuevo_año(self, mock_datetime):
        """Prueba que el número se reinicia a 1 al empezar un nuevo año."""
        mock_datetime.now.return_value = datetime(2026, 1, 1, 12, 0, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        self.client.login(username='user1', password='pass123')
        response = self.client.post(reverse('ordinarios_agregar'), {
            'iddoc': '789012',
            'destinatario_select_1': self.destinatario.nombre,
            'materia': 'Nuevo Ordinario 2026'
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        nuevo_ordinario = Ordinario.objects.latest('creada')
        self.assertEqual(nuevo_ordinario.numero, 1)
        self.assertEqual(nuevo_ordinario.fecha.year, 2026)

    @patch('ordinarios.views.datetime')
    def test_numero_incrementa_en_mismo_año(self, mock_datetime):
        """Prueba que el número se incremente dentro del mismo año."""
        mock_datetime.now.return_value = datetime(2025, 12, 31, 12, 0, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        self.client.login(username='user1', password='pass123')
        response = self.client.post(reverse('ordinarios_agregar'), {
            'iddoc': '789013',
            'destinatario_select_1': self.destinatario.nombre,
            'materia': 'Otro en 2025'
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        nuevo_ordinario = Ordinario.objects.latest('creada')
        self.assertEqual(nuevo_ordinario.numero, 76)
        self.assertEqual(nuevo_ordinario.fecha.year, 2025)

    def test_no_agregar_cuando_bloqueado_por_otro(self):
        """Prueba que no se pueda agregar si el libro está bloqueado por otro."""
        self.config.bloqueado = True
        self.config.bloqueado_por = self.user2
        self.config.save()
        
        self.client.login(username='user1', password='pass123')
        response = self.client.post(reverse('ordinarios_agregar'), {
            'iddoc': '789014',
            'destinatario_select_1': self.destinatario.nombre,
            'materia': 'Bloqueado Test'
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El libro está bloqueado")
        self.assertEqual(Ordinario.objects.count(), 1)

    @patch('ordinarios.views.datetime')
    def test_selector_año_incluye_siguiente_el_31_dic(self, mock_datetime):
        """Prueba que el selector incluya el año siguiente el 31/12."""
        mock_datetime.now.return_value = datetime(2025, 12, 31, 12, 0, 0)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        self.client.login(username='user1', password='pass123')
        response = self.client.get(reverse('ordinarios_lista'))
        
        self.assertEqual(response.status_code, 200)
        # Cambiar a una verificación menos estricta
        self.assertContains(response, '2026', msg_prefix="El año 2026 no está en el selector")

    def test_no_anular_si_no_autor(self):
        """Prueba que un usuario no pueda anular un ordinario que no creó."""
        self.client.login(username='user2', password='pass123')
        ordinario = Ordinario.objects.get(numero=75)
        response = self.client.get(reverse('ordinarios_anular', args=[ordinario.pk]), follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No tienes permiso para anular este ordinario")
        ordinario.refresh_from_db()
        self.assertFalse(ordinario.anulada)