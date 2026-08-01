"""
Management command: python manage.py seed_users

Creates one test user per role (safe to re-run — uses get_or_create).
Also seeds AssessmentCriteria via seed_criteria logic.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


TEST_USERS = [
    # (username, email, password, role, first, last, extra_fields)
    (
        'admin', 'admin@example.com', 'admin123',
        'coordinator',   # superuser has no role; set coordinator as fallback
        'System', 'Admin',
        {'is_staff': True, 'is_superuser': True, 'staff_id': 'SYS001'},
    ),
    (
        'coordinator', 'coordinator@example.com', 'coordinator123',
        'coordinator', 'Grace', 'Adeyemi',
        {'staff_id': 'CO001', 'faculty': 'Engineering & Technology'},
    ),
    (
        'supervisor', 'supervisor@example.com', 'supervisor123',
        'supervisor', 'Michael', 'Okonkwo',
        {
            'company_name':    'TechCorp Nigeria Ltd',
            'company_address': '12 Ozumba Mbadiwe Ave, Victoria Island, Lagos',
            'job_title':       'Senior Software Engineer',
        },
    ),
    (
        'student', 'student@example.com', 'student123',
        'student', 'Amara', 'Eze',
        {
            'matric_number': 'ENG/2022/0042',
            'department':    'Computer Engineering',
            'level':         'HND 2',
        },
    ),
]


class Command(BaseCommand):
    help = 'Seed one test user per role for development / demo purposes.'

    def handle(self, *args, **options):
        User = get_user_model()
        created_count = 0

        for username, email, password, role, first, last, extras in TEST_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email':      email,
                    'role':       role,
                    'first_name': first,
                    'last_name':  last,
                    **extras,
                }
            )
            if created:
                user.set_password(password)
                user.save()
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Created [{role:12s}] {username} / {password}'
                    )
                )
            else:
                self.stdout.write(
                    f'  Exists  [{role:12s}] {username}'
                )

        # Also run seed_criteria
        self.stdout.write('\nSeeding assessment criteria…')
        from django.core.management import call_command
        call_command('seed_criteria', verbosity=0)
        self.stdout.write(self.style.SUCCESS('  Criteria seeded.'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. {created_count} user(s) created.'
            )
        )
