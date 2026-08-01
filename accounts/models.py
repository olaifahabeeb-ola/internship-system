from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


# ── Shared choices ────────────────────────────────────────────────────────────

DEPARTMENT_CHOICES = [
    ('All Departments',                  'All Departments'),
    ('Computer Science',                 'Computer Science'),
    ('Software and Web Development',     'Software and Web Development'),
    ('Business Administration',          'Business Administration'),
    ('Accountancy',                      'Accountancy'),
    ('Electrical/Electronic Engineering','Electrical/Electronic Engineering'),
    ('Mechanical Engineering',           'Mechanical Engineering'),
    ('Civil Engineering',                'Civil Engineering'),
    ('Science Laboratory Technology',    'Science Laboratory Technology'),
    ('Statistics',                       'Statistics'),
    ('Mass Communication',               'Mass Communication'),
    ('Office Technology and Management', 'Office Technology and Management'),
    ('Marketing',                        'Marketing'),
]

PROGRAMME_CHOICES = [
    ('Both', 'Both (ND & HND)'),
    ('ND',   'ND'),
    ('HND',  'HND'),
]

LEVEL_CHOICES = [
    ('All Levels', 'All Levels'),
    ('ND1',        'ND 1'),
    ('ND2',        'ND 2'),
    ('HND1',       'HND 1'),
    ('HND2',       'HND 2'),
]

# Used by coordinators AND (now) supervisors — anyone who must be
# locked to exactly ONE real department, never the 'All Departments'
# wildcard.
FACULTY_CHOICES = [c for c in DEPARTMENT_CHOICES if c[0] != 'All Departments']


class CustomUser(AbstractUser):
    """
    Single user model for all roles.
    NOTE: Admin is NOT stored in `role` — it is represented purely by
    Django's built-in is_superuser / is_staff flags.
    """

    ROLE_CHOICES = [
        ('student',     'Student'),
        ('supervisor',  'Industry Supervisor'),
        ('coordinator', 'School Coordinator'),
    ]

    role  = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True)

    # ── Student fields ────────────────────────────────────────────
    matric_number    = models.CharField(max_length=50, blank=True, unique=False)
    department       = models.CharField(
        max_length=100,
        choices=DEPARTMENT_CHOICES,
        blank=True,
        default='',
    )
    programme        = models.CharField(
        max_length=10,
        choices=[('ND', 'ND'), ('HND', 'HND')],
        blank=True,
        default='',
    )
    level            = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        blank=True,
        default='',
    )
    academic_session = models.CharField(
        max_length=20,
        blank=True,
        default='2024/2025',
        help_text="e.g. 2024/2025",
    )

    # ── Supervisor fields ─────────────────────────────────────────
    company_name          = models.CharField(max_length=150, blank=True)
    company_address       = models.TextField(blank=True)
    job_title              = models.CharField(max_length=100, blank=True)
    supervisor_department  = models.CharField(
        max_length=100,
        choices=FACULTY_CHOICES,
        blank=True,
        default='',
        help_text=(
            "The one department this supervisor posts placements for. "
            "Every placement they submit automatically targets this "
            "department — it cannot be changed per-posting."
        ),
    )

    # ── Coordinator fields ────────────────────────────────────────
    staff_id = models.CharField(max_length=20, blank=True)
    faculty  = models.CharField(
        max_length=100,
        choices=FACULTY_CHOICES,
        blank=True,
        default='',
        help_text=(
            "Coordinator's department. Must match student department "
            "exactly for filtering to work — hence this is a dropdown, "
            "not free text."
        ),
    )

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display() if self.role else 'Admin'})"

    def clean(self):
        """
        Model-level guardrail: no matter which form, view, or script
        creates/saves a user, a student MUST have a department, a
        coordinator MUST have a faculty, and now a supervisor MUST
        have a supervisor_department. This is the last line of
        defense against a future form/template change silently
        producing a blank value again.
        """
        super().clean()
        errors = {}
        if self.role == 'student' and not self.department:
            errors['department'] = 'Students must have a department set.'
        if self.role == 'coordinator' and not self.faculty:
            errors['faculty'] = 'Coordinators must have a department (faculty) set.'
        if self.role == 'supervisor' and not self.supervisor_department:
            errors['supervisor_department'] = 'Supervisors must have a department set.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Only enforce the guardrail on a FULL save, or a partial save
        that explicitly touches the relevant field via update_fields.
        This matters because Django's login flow does
        `user.save(update_fields=['last_login'])` on every login — 
        without this check, that harmless timestamp update would crash
        for any existing account that has a blank department/faculty/
        supervisor_department, locking real users out of logging in.
        """
        update_fields = kwargs.get('update_fields')
        touches_role_fields = (
            update_fields is None
            or 'role' in update_fields
            or 'department' in update_fields
            or 'faculty' in update_fields
            or 'supervisor_department' in update_fields
        )
        if touches_role_fields and self.role in ('student', 'coordinator', 'supervisor'):
            self.clean()
        super().save(*args, **kwargs)

    @property
    def is_admin(self):
        return self.is_superuser or self.is_staff

    @property
    def is_student(self):
        return self.role == 'student' and not self.is_admin

    @property
    def is_supervisor(self):
        return self.role == 'supervisor' and not self.is_admin

    @property
    def is_coordinator(self):
        return self.role == 'coordinator' and not self.is_admin

    @property
    def has_department(self):
        return bool(self.department and self.department != 'All Departments')