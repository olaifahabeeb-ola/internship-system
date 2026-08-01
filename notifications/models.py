from django.db import models
from accounts.models import CustomUser


class Notification(models.Model):
    TYPE_CHOICES = [
        ('application',  'Application Update'),
        ('logbook',      'Logbook Review'),
        ('assessment',   'Assessment'),
        ('announcement', 'Announcement'),
        ('placement',    'Placement'),
        ('reminder',     'Reminder'),
    ]

    user              = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    message           = models.CharField(max_length=255)
    notification_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='application'
    )
    link              = models.CharField(
        max_length=255, blank=True,
        help_text="Relative URL to open when the notification is clicked.",
    )
    is_read           = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.get_notification_type_display()} | {self.message[:40]}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])