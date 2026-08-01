"""
Management command: python manage.py seed_criteria

Creates the default AssessmentCriteria rows if they don't already exist.
Safe to run multiple times (uses get_or_create).
"""
from django.core.management.base import BaseCommand
from assessment.models import AssessmentCriteria


CRITERIA = [
    # (name, description, category, order)
    (
        'Punctuality',
        'Reports to work on time and meets all deadlines.',
        'soft_skills', 1,
    ),
    (
        'Attendance',
        'Regular presence at the workplace; minimises absenteeism.',
        'soft_skills', 2,
    ),
    (
        'Teamwork & Collaboration',
        'Works effectively with colleagues and contributes positively to the team.',
        'soft_skills', 3,
    ),
    (
        'Communication Skills',
        'Communicates ideas clearly in both written and verbal form.',
        'soft_skills', 4,
    ),
    (
        'Initiative & Proactiveness',
        'Identifies tasks without being asked; shows drive and enthusiasm.',
        'soft_skills', 5,
    ),
    (
        'Adaptability / Flexibility',
        'Adjusts quickly to new tasks, processes, or priorities.',
        'soft_skills', 6,
    ),
    (
        'Professionalism & Conduct',
        'Maintains a professional attitude, dress, and behaviour.',
        'soft_skills', 7,
    ),
    (
        'Technical / Job Skills',
        'Demonstrates the technical competencies required for the role.',
        'technical_skills', 8,
    ),
    (
        'Quality of Work',
        'Produces accurate, thorough, and high-quality output.',
        'technical_skills', 9,
    ),
    (
        'Problem Solving',
        'Analyses problems effectively and proposes practical solutions.',
        'technical_skills', 10,
    ),
]


class Command(BaseCommand):
    help = 'Seed default AssessmentCriteria rows.'

    def handle(self, *args, **options):
        created_count = 0
        for name, description, category, order in CRITERIA:
            obj, created = AssessmentCriteria.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'category':    category,
                    'max_score':   10,
                    'order':       order,
                    'is_active':   True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created: {name}'))
            else:
                self.stdout.write(f'  Exists:  {name}')

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. {created_count} criteria created, '
                f'{len(CRITERIA) - created_count} already existed.'
            )
        )
