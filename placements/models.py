from django.db import models
from django.utils import timezone
from accounts.models import CustomUser, DEPARTMENT_CHOICES, PROGRAMME_CHOICES, LEVEL_CHOICES
from cloudinary_storage.storage import RawMediaCloudinaryStorage

# Real, concrete departments only — 'All Departments' is deliberately
# excluded here. Placement targeting is now always strict: a student
# only ever sees placements tagged for their exact department, never
# a shared/general listing. Offering 'All Departments' as a choice
# would let someone create a placement that's permanently invisible
# to every student, so it's removed from the options entirely.
TARGETABLE_DEPARTMENT_CHOICES = [c for c in DEPARTMENT_CHOICES if c[0] != 'All Departments']


class Placement(models.Model):
    STATUS_CHOICES = [
        ('open',   'Open'),
        ('closed', 'Closed'),
    ]

    # Approval workflow — SEPARATE from STATUS_CHOICES above.
    # STATUS_CHOICES = is this currently accepting applications?
    # APPROVAL_STATUS_CHOICES = has a coordinator authorized this
    # listing to exist/be visible at all? A placement can be
    # 'approved' + 'closed' (fully authorized, just not taking
    # applicants right now), but it can never be visible to students
    # while still 'pending' or 'rejected', regardless of STATUS.
    APPROVAL_STATUS_CHOICES = [
        ('pending',  'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    title           = models.CharField(max_length=200)
    company_name    = models.CharField(max_length=150)
    description     = models.TextField()
    required_skills = models.TextField(blank=True)
    location        = models.CharField(max_length=150)
    start_date      = models.DateField()
    end_date        = models.DateField()
    slots_available = models.PositiveIntegerField(default=1)
    status          = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='open'
    )

    # ── Ownership / management ──────────────────────────────────
    # posted_by / created_by are NULLABLE. They stay populated from
    # creation for coordinator-made placements (unchanged behaviour).
    # For supervisor-submitted placements, both start NULL —
    # "unclaimed" — and only get set when a coordinator approves the
    # submission (see approve() below). This means every existing
    # coordinator-scoped query in views.py keeps working unmodified:
    # a pending supervisor submission simply doesn't show up anywhere
    # yet, and the moment it's approved it behaves exactly like a
    # normal coordinator listing.
    posted_by       = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='posted_placements',
        limit_choices_to={'role': 'coordinator'},
        null=True,
        blank=True,
    )
    created_by      = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='created_placements',
        limit_choices_to={'role': 'coordinator'},
        null=True,
        blank=True,
    )

    # Who actually typed this listing in — a coordinator OR a
    # supervisor. Pure audit trail; never used for dashboard scoping.
    submitted_by    = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='submitted_placements',
        limit_choices_to={'role__in': ['coordinator', 'supervisor']},
        null=True,
        blank=True,
        help_text="Whoever originally submitted this listing — coordinator or supervisor.",
    )

    # ── Supervisor pre-assignment ─────────────────────────────────
    assigned_supervisor = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='assigned_placements',
        limit_choices_to={'role': 'supervisor'},
        null=True,
        blank=True,
        help_text="The industry supervisor responsible for students in this placement",
    )

    # ── Approval workflow ────────────────────────────────────────
    # Default 'approved' is deliberate: it's a no-op for every
    # placement created via the existing coordinator flow, and for
    # every row that already exists in the database before this
    # migration runs. Only the new supervisor-submission view
    # explicitly sets 'pending'.
    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS_CHOICES,
        default='approved',
    )
    reviewed_by     = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_placements',
        limit_choices_to={'role': 'coordinator'},
    )
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    approval_notes  = models.TextField(
        blank=True,
        help_text="Optional note shown to the supervisor, e.g. reason for rejection.",
    )

    # ── Department targeting ──────────────────────────────────────
    target_department = models.CharField(
        max_length=100,
        choices=TARGETABLE_DEPARTMENT_CHOICES,
        default='',
        help_text=(
            "Which single department is this placement for. Only "
            "students in this exact department will see it — there "
            "is no 'show to everyone' option."
        ),
    )
    target_programme  = models.CharField(
        max_length=10,
        choices=PROGRAMME_CHOICES,
        default='Both',
        help_text="ND, HND, or Both.",
    )
    target_level      = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        default='All Levels',
        help_text="Specific level or All Levels.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} @ {self.company_name}"

    @property
    def accepted_count(self):
        return self.applications.filter(status='accepted').count()

    @property
    def slots_remaining(self):
        return max(0, self.slots_available - self.accepted_count)

    @property
    def is_full(self):
        return self.slots_remaining == 0

    @property
    def is_open(self):
        return self.status == 'open'

    @property
    def is_pending(self):
        return self.approval_status == 'pending'

    @property
    def is_approved(self):
        return self.approval_status == 'approved'

    @property
    def is_rejected(self):
        return self.approval_status == 'rejected'

    @property
    def submitted_by_supervisor(self):
        """True if this listing originated from a supervisor, not a coordinator."""
        return bool(self.submitted_by_id and self.submitted_by.role == 'supervisor')

    def skills_list(self):
        if not self.required_skills:
            return []
        return [s.strip() for s in self.required_skills.split(',') if s.strip()]

    def matching_supervisors(self):
        """
        Supervisors whose registered company matches this placement's
        company name, used as a fallback when no supervisor was
        pre-assigned at posting time.
        """
        return CustomUser.objects.filter(
            role='supervisor',
            company_name__iexact=self.company_name.strip(),
        )

    def approve(self, coordinator, notes=''):
        """
        Approve a pending (usually supervisor-submitted) placement.
        Claims ownership for the approving coordinator — from this
        point on, this placement behaves exactly like one the
        coordinator created directly.
        """
        self.approval_status = 'approved'
        self.reviewed_by     = coordinator
        self.reviewed_at     = timezone.now()
        self.approval_notes  = notes
        self.posted_by       = coordinator
        self.created_by      = coordinator
        self.save()

    def reject(self, coordinator, notes=''):
        """
        Reject a pending placement submission. Ownership is
        deliberately left unclaimed (posted_by/created_by stay null)
        since a rejected listing shouldn't appear in any coordinator's
        management queue.
        """
        self.approval_status = 'rejected'
        self.reviewed_by     = coordinator
        self.reviewed_at     = timezone.now()
        self.approval_notes  = notes
        self.save()

    def is_visible_to_student(self, student):
        """
        Returns True if this placement should be shown to the given student.

        Department matching is STRICT — visible only if target_department
        exactly matches the student's own department. There is no
        'All Departments' wildcard.

        Rules:
          - Must be approved AND open — pending/rejected/closed placements
            are never visible to students, regardless of targeting.
          - target_department must exactly equal the student's department.
          - target_programme matches (or is 'Both').
          - target_level matches (or is 'All Levels').
        """
        if self.approval_status != 'approved':
            return False

        if self.status != 'open':
            return False

        # Department check — STRICT exact match, no wildcard.
        if self.target_department != student.department:
            return False

        # Programme check
        if (self.target_programme != 'Both'
                and student.programme
                and self.target_programme != student.programme):
            return False

        # Level check
        if (self.target_level != 'All Levels'
                and student.level
                and self.target_level != student.level):
            return False

        return True


class Application(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    student      = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE,
        related_name='applications',
        limit_choices_to={'role': 'student'},
    )
    placement    = models.ForeignKey(
        Placement, on_delete=models.CASCADE,
        related_name='applications',
    )
    cover_letter = models.TextField(blank=True)
    cv           = models.FileField(
        upload_to='cvs/', blank=True, null=True,
        storage=RawMediaCloudinaryStorage(),
    )
    status       = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending'
    )
    applied_at   = models.DateTimeField(auto_now_add=True)
    reviewed_by  = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_applications',
        limit_choices_to={'role': 'coordinator'},
    )
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    supervisor   = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='supervised_students',
        limit_choices_to={'role': 'supervisor'},
    )

    class Meta:
        unique_together = ('student', 'placement')
        ordering        = ['-applied_at']

    def __str__(self):
        return (f"{self.student.get_full_name()} → "
                f"{self.placement.title} [{self.get_status_display()}]")

    def mark_reviewed(self, coordinator, status, notes=''):
        self.reviewed_by  = coordinator
        self.reviewed_at  = timezone.now()
        self.status       = status
        self.review_notes = notes
        self.save()