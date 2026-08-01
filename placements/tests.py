from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Placement


class CoordinatorPlacementPostingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.coordinator = User.objects.create_user(
            username='coord_post_test',
            email='coord_post@example.com',
            password='testpass123',
            first_name='Coord',
            last_name='Test',
            role='coordinator',
            department='Computer Science',
        )

    def test_coordinator_can_post_and_see_placement_on_dashboard(self):
        self.client.force_login(self.coordinator)

        response = self.client.post(
            reverse('placements:create'),
            {
                'title': 'Software Development Intern',
                'company_name': 'TechCorp',
                'description': 'Build products for the company.',
                'required_skills': 'Python, Django',
                'location': 'Lagos',
                'start_date': '2026-08-01',
                'end_date': '2026-09-30',
                'slots_available': 3,
                'target_department': 'Computer Science',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:coordinator_dashboard'))

        placement = Placement.objects.get(title='Software Development Intern')
        self.assertEqual(placement.created_by, self.coordinator)
        self.assertEqual(placement.posted_by, self.coordinator)
        self.assertEqual(placement.target_department, 'Computer Science')

        dashboard = self.client.get(reverse('accounts:coordinator_dashboard'))
        self.assertContains(dashboard, 'Software Development Intern')
