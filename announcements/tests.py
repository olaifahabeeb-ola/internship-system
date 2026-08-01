from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Announcement


class AnnouncementVisibilityTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.coordinator = User.objects.create_user(
            username='coord1',
            email='coord@example.com',
            password='testpass123',
            first_name='Coord',
            last_name='One',
            role='coordinator',
            department='Computer Science',
        )

        self.student_cs = User.objects.create_user(
            username='studentcs',
            email='cs@example.com',
            password='testpass123',
            first_name='CS',
            last_name='Student',
            role='student',
            department='Computer Science',
        )

        self.student_bus = User.objects.create_user(
            username='studentbus',
            email='bus@example.com',
            password='testpass123',
            first_name='Bus',
            last_name='Student',
            role='student',
            department='Business Administration',
        )

    def test_student_only_sees_department_specific_announcements(self):
        Announcement.objects.create(
            title='CS Only',
            message='Computer Science announcement',
            posted_by=self.coordinator,
            target_audience='specific_department',
            target_department='Computer Science',
        )
        Announcement.objects.create(
            title='Business Only',
            message='Business announcement',
            posted_by=self.coordinator,
            target_audience='specific_department',
            target_department='Business Administration',
        )
        Announcement.objects.create(
            title='All Departments',
            message='Everyone sees this',
            posted_by=self.coordinator,
            target_audience='all',
        )

        visible = list(Announcement.for_user(self.student_cs))

        self.assertEqual([ann.title for ann in visible], ['CS Only', 'All Departments'])
        self.assertNotIn('Business Only', [ann.title for ann in visible])

        visible_bus = list(Announcement.for_user(self.student_bus))
        self.assertEqual([ann.title for ann in visible_bus], ['Business Only', 'All Departments'])
