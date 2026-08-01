from django.test import TestCase
from django.urls import reverse

from .models import CustomUser


class DashboardRoutingTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='testpass123',
            role='coordinator',
            is_staff=True,
            is_superuser=True,
        )

    def test_superuser_dashboard_renders_admin_template(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('accounts:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/admin_dashboard.html')


class AuthPageAssetTests(TestCase):
    def test_auth_templates_use_static_background_asset(self):
        pages = [
            ('accounts:login', 'login'),
            ('accounts:register', 'register'),
            ('accounts:password_reset', 'password_reset'),
        ]

        for url_name, _ in pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'auth-illustration.svg')
