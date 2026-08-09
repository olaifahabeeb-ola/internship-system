from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import CustomUser
from placements.models import Application
from cloudinary_storage.storage import RawMediaCloudinaryStorage


class LogbookEntry(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='log_entries',
    )
    date                 = models.DateField()
    activity_description = models.TextField()
    skills_gained        = models.CharField(max_length=300, blank=True)
    hours_worked         = models.DecimalField(max_digits=4, decimal_places=1)
    attachment           = models.FileField(
        upload_to='logbook_attachments/',
        blank=True, null=True,
        storage=RawMediaCloudinaryStorage(),
    )
    status             = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending'
    )
    supervisor_comment = models.TextField(blank=True)
    reviewed_by        = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_log_entries',
        limit_choices_to={'role': 'supervisor'},
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('application', 'date')
        ordering        = ['-date']
        verbose_name    = 'Logbook Entry'
        verbose_name_plural = 'Logbook Entries'

    def __str__(self):
        return (
            f"{self.application.student.get_full_name()} | "
            f"{self.date} | {self.get_status_display()}"
        )

    @property
    def student(self):
        return self.application.student

    @property
    def placement(self):
        return self.application.placement

    @property
    def is_editable(self):
        return self.status == 'pending'

    # Validation is handled in forms.py and views.py — NOT in save()
    # to avoid RelatedObjectDoesNotExist when application is not yet
    # committed to the database during form.save(commit=False)

    def mark_reviewed(self, supervisor, status, comment=''):
        self.reviewed_by        = supervisor
        self.reviewed_at        = timezone.now()
        self.status             = status
        self.supervisor_comment = comment
        super().save(update_fields=[
            'reviewed_by', 'reviewed_at', 'status', 'supervisor_comment'
        ])


class WeeklyReport(models.Model):
    application        = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='weekly_reports',
    )
    week_start          = models.DateField()
    week_end            = models.DateField()
    summary             = models.TextField()
    challenges_faced    = models.TextField(blank=True)
    next_week_plan      = models.TextField(blank=True)
    supervisor_approved = models.BooleanField(default=False)
    supervisor_comment  = models.TextField(blank=True)
    reviewed_by         = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_weekly_reports',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('application', 'week_start')
        ordering        = ['-week_start']
        verbose_name    = 'Weekly Report'

    def __str__(self):
        return (
            f"{self.application.student.get_full_name()} | "
            f"Week of {self.week_start}"
        )

    @property
    def student(self):
        return self.application.student

    @property
    def placement(self):
        return self.application.placement
