from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from placements.models import Application


# ══════════════════════════════════════════════════════════════════
#  ASSESSMENT CRITERIA  (seeded via management command)
# ══════════════════════════════════════════════════════════════════

class AssessmentCriteria(models.Model):
    CATEGORY_CHOICES = [
        ('soft_skills',      'Soft Skills'),
        ('technical_skills', 'Technical Skills'),
    ]

    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    max_score   = models.PositiveSmallIntegerField(default=10)
    category    = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='soft_skills'
    )
    order       = models.PositiveSmallIntegerField(
        default=0, help_text="Display order on the assessment form."
    )
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering    = ['order', 'category', 'name']
        verbose_name        = 'Assessment Criterion'
        verbose_name_plural = 'Assessment Criteria'

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


# ══════════════════════════════════════════════════════════════════
#  ASSESSMENT  (one mid-term + one final per student per placement)
# ══════════════════════════════════════════════════════════════════

class Assessment(models.Model):
    TYPE_CHOICES = [
        ('mid_term', 'Mid-Term Assessment'),
        ('final',    'Final Assessment'),
    ]
    STATUS_CHOICES = [
        ('draft',     'Draft'),
        ('submitted', 'Submitted'),
    ]

    application       = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='assessments',
    )
    supervisor        = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='assessments_given',
        limit_choices_to={'role': 'supervisor'},
    )
    assessment_type   = models.CharField(
        max_length=10, choices=TYPE_CHOICES
    )
    status            = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='draft'
    )
    total_score       = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Sum of all criterion scores."
    )
    max_possible      = models.PositiveSmallIntegerField(
        default=0, help_text="Sum of all max_scores at time of submission."
    )
    submission_date   = models.DateTimeField(auto_now_add=True)
    last_modified     = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together     = ('application', 'assessment_type')
        ordering            = ['-submission_date']

    def __str__(self):
        return (
            f"{self.application.student.get_full_name()} | "
            f"{self.get_assessment_type_display()} | {self.get_status_display()}"
        )

    @property
    def student(self):
        return self.application.student

    @property
    def placement(self):
        return self.application.placement

    @property
    def percentage(self):
        if self.max_possible == 0:
            return 0
        return round((float(self.total_score) / self.max_possible) * 100, 1)

    @property
    def grade_letter(self):
        pct = self.percentage
        if pct >= 70: return 'A'
        if pct >= 60: return 'B'
        if pct >= 50: return 'C'
        if pct >= 45: return 'D'
        return 'F'

    @property
    def is_submitted(self):
        return self.status == 'submitted'

    def recalculate_totals(self):
        """Re-sum scores from AssessmentScore rows — call after saving scores."""
        scores = self.scores.select_related('criterion')
        self.total_score  = sum(s.score for s in scores)
        self.max_possible = sum(s.criterion.max_score for s in scores)
        Assessment.objects.filter(pk=self.pk).update(
            total_score=self.total_score,
            max_possible=self.max_possible,
        )


# ══════════════════════════════════════════════════════════════════
#  ASSESSMENT SCORE  (one row per criterion per assessment)
# ══════════════════════════════════════════════════════════════════

class AssessmentScore(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='scores',
    )
    criterion  = models.ForeignKey(
        AssessmentCriteria,
        on_delete=models.CASCADE,
        related_name='scores',
    )
    # Only a universal floor of 0 is a fixed validator — the ceiling
    # depends on which criterion this is, so it can't be expressed as
    # a static MaxValueValidator. It used to be hardcoded to 10 here,
    # which Django admin's ModelForm would enforce via full_clean()
    # even though a criterion could legitimately be worth more or
    # less. See clean() below for the real, dynamic check — this is
    # what Django admin, and any future form, will actually run.
    score      = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0)]
    )
    comment    = models.TextField(
        blank=True,
        help_text="Optional feedback specific to this criterion."
    )

    class Meta:
        unique_together = ('assessment', 'criterion')

    def __str__(self):
        return (
            f"{self.assessment.student.get_full_name()} | "
            f"{self.criterion.name}: {self.score}/{self.criterion.max_score}"
        )

    def clean(self):
        super().clean()
        if self.score is not None and self.criterion_id and self.score > self.criterion.max_score:
            raise ValidationError({
                'score': f'Score must be between 0 and {self.criterion.max_score} '
                         f'for "{self.criterion.name}".'
            })

    @property
    def percentage(self):
        if self.criterion.max_score == 0:
            return 0
        return round((self.score / self.criterion.max_score) * 100, 1)

    @property
    def colour_class(self):
        """Bootstrap colour class based on percentage."""
        pct = self.percentage
        if pct >= 70: return 'success'
        if pct >= 50: return 'warning'
        return 'danger'


# ══════════════════════════════════════════════════════════════════
#  ASSESSMENT SUMMARY  (overall feedback — 1-to-1 with Assessment)
# ══════════════════════════════════════════════════════════════════

class AssessmentSummary(models.Model):
    RECOMMENDATION_CHOICES = [
        ('excellent',        'Excellent'),
        ('good',             'Good'),
        ('satisfactory',     'Satisfactory'),
        ('needs_improvement','Needs Improvement'),
        ('unsatisfactory',   'Unsatisfactory'),
    ]

    assessment     = models.OneToOneField(
        Assessment,
        on_delete=models.CASCADE,
        related_name='summary',
    )
    overall_comment       = models.TextField(blank=True)
    strengths             = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    recommendation        = models.CharField(
        max_length=20,
        choices=RECOMMENDATION_CHOICES,
        default='satisfactory',
    )

    student_acknowledged    = models.BooleanField(default=False)
    student_acknowledged_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"Summary: {self.assessment.student.get_full_name()} | "
            f"{self.get_recommendation_display()}"
        )

    def acknowledge(self):
        """Mark that the student has read the assessment."""
        self.student_acknowledged    = True
        self.student_acknowledged_at = timezone.now()
        self.save(update_fields=['student_acknowledged', 'student_acknowledged_at'])

    @property
    def recommendation_colour(self):
        return {
            'excellent':         'success',
            'good':              'primary',
            'satisfactory':      'info',
            'needs_improvement': 'warning',
            'unsatisfactory':    'danger',
        }.get(self.recommendation, 'secondary')