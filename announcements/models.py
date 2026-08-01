from django.db import models
from accounts.models import CustomUser


class Announcement(models.Model):
    AUDIENCE_CHOICES = [
        ('all',                 'Everyone'),
        ('students',            'Students Only (My Department)'),
        ('supervisors',         'All Supervisors'),
        ('specific_department', 'Specific Department'),
        ('specific_student',    'Specific Student'),
        ('specific_supervisor', 'Specific Supervisor'),
    ]
    PRIORITY_CHOICES = [
        ('normal',    'Normal'),
        ('important', 'Important'),
        ('urgent',    'Urgent'),
    ]
    PRIORITY_COLOURS = {
        'normal':    'primary',
        'important': 'warning',
        'urgent':    'danger',
    }

    title           = models.CharField(max_length=200)
    message         = models.TextField()
    posted_by       = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='announcements',
        limit_choices_to={'role': 'coordinator'},
    )
    target_audience = models.CharField(
        max_length=25, choices=AUDIENCE_CHOICES, default='all'
    )
    specific_user   = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='targeted_announcements',
    )
    target_department = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Used when targeting a specific department.',
    )
    priority  = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default='normal'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            models.Case(
                models.When(priority='urgent',    then=0),
                models.When(priority='important', then=1),
                default=2,
                output_field=models.IntegerField(),
            ),
            '-created_at',
        ]

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title}"

    @property
    def priority_colour(self):
        return self.PRIORITY_COLOURS.get(self.priority, 'secondary')

    @property
    def is_new(self):
        from django.utils import timezone
        from datetime import timedelta
        return self.created_at >= timezone.now() - timedelta(hours=48)

    @classmethod
    def for_user(cls, user):
        """
        Return active announcements visible to the given user.

        Department / affiliation scoping rules — EVERY bulk audience
        type is scoped to the posting coordinator's own department,
        never system-wide:

        - 'all' and 'students' both mean "my department's students" —
          a student only ever sees these from the coordinator whose
          faculty matches their own department.
        - 'all' and 'supervisors' both mean "supervisors affiliated
          with my department's placements" — a supervisor only sees
          these from coordinator(s) they're actually attached to via
          an accepted application, never every coordinator system-wide.
        - 'specific_department' matches the student's department exactly.
        - 'specific_student' / 'specific_supervisor' match one named user.
        - Coordinators always see every one of their own posts,
          regardless of audience type.
        """
        from django.db.models import Case, IntegerField, Q, When

        if user.is_student:
            return (
                cls.objects.filter(is_active=True)
                .filter(
                    (
                        Q(target_audience__in=['all', 'students']) &
                        (Q(posted_by__department=user.department) |
                         Q(posted_by__faculty=user.department))
                    ) |
                    (
                        Q(target_audience='specific_department') &
                        Q(target_department=user.department)
                    ) |
                    Q(target_audience='specific_student', specific_user=user)
                )
                .annotate(
                    audience_priority=Case(
                        When(target_audience='specific_department', then=0),
                        When(target_audience='specific_student', then=1),
                        When(target_audience='students', then=2),
                        When(target_audience='all', then=3),
                        default=4,
                        output_field=IntegerField(),
                    )
                )
                .order_by('audience_priority', '-created_at')
            )

        elif user.is_supervisor:
            # Deferred import — avoids a circular import between the
            # announcements and placements apps, matching the same
            # pattern already used elsewhere in this codebase (e.g.
            # accounts/views.py's dashboard functions).
            from placements.models import Application

            # Coordinators this supervisor is actually affiliated with
            # — i.e. they're the assigned supervisor on at least one
            # accepted application under that coordinator's placements.
            # 'all'/'supervisors' broadcasts are scoped to ONLY these
            # coordinators, never every coordinator in the system.
            affiliated_coordinator_ids = Application.objects.filter(
                supervisor=user,
                status='accepted',
            ).values_list('placement__posted_by_id', flat=True).distinct()

            return cls.objects.filter(is_active=True).filter(
                (
                    Q(target_audience__in=['all', 'supervisors']) &
                    Q(posted_by_id__in=affiliated_coordinator_ids)
                ) |
                Q(target_audience='specific_supervisor', specific_user=user)
            )

        elif user.is_coordinator:
            # Coordinators see only their own announcements
            return cls.objects.filter(
                is_active=True,
                posted_by=user,
            )

        return cls.objects.none()