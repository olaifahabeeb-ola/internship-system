import os
from django import forms
from django.conf import settings
from django.utils import timezone
from .models import LogbookEntry, WeeklyReport


class LogbookEntryForm(forms.ModelForm):
    """Student submits or edits a daily log entry."""

    class Meta:
        model  = LogbookEntry
        fields = ['activity_description', 'skills_gained',
                  'hours_worked', 'attachment']
        widgets = {
            'activity_description': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Describe the tasks you performed today in detail...'
            }),
            'skills_gained': forms.TextInput(attrs={
                'placeholder': 'e.g. Python debugging, stakeholder communication'
            }),
            'hours_worked': forms.NumberInput(attrs={
                'min': 1, 'max': 24, 'step': '0.5', 'placeholder': '8'
            }),
        }
        labels = {
            'activity_description': 'Activities Performed',
            'skills_gained':        'Skills Applied / Gained',
            'hours_worked':         'Hours Worked',
            'attachment':           'Attachment (optional)',
        }

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if not attachment:
            return attachment

        ext = os.path.splitext(attachment.name)[1].lower().lstrip('.')
        allowed = getattr(settings, 'LOGBOOK_ALLOWED_EXTENSIONS',
                          ['pdf', 'jpg', 'jpeg', 'png', 'docx'])
        if ext not in allowed:
            raise forms.ValidationError(
                f"Only {', '.join(a.upper() for a in allowed)} files are allowed."
            )
        max_bytes = getattr(settings, 'LOGBOOK_MAX_SIZE_BYTES', 5 * 1024 * 1024)
        if attachment.size > max_bytes:
            raise forms.ValidationError(
                f"File must not exceed "
                f"{getattr(settings, 'LOGBOOK_MAX_SIZE_MB', 5)} MB."
            )
        return attachment

    def clean_hours_worked(self):
        hours = self.cleaned_data.get('hours_worked')
        if hours is not None and (hours < 1 or hours > 24):
            raise forms.ValidationError("Hours worked must be between 1 and 24.")
        return hours



class ReviewLogEntryForm(forms.Form):
    """Supervisor approves or rejects a log entry."""
    STATUS_CHOICES = [
        ('approved', 'Approve'),
        ('rejected', 'Reject'),
    ]
    status  = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.RadioSelect,
        label='Decision',
    )
    supervisor_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Add feedback for the student (required if rejecting)...'
        }),
        label='Comment',
    )

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get('status') == 'rejected'
                and not cleaned.get('supervisor_comment', '').strip()):
            self.add_error(
                'supervisor_comment',
                'A comment is required when rejecting a log entry.'
            )
        return cleaned


class BulkApproveForm(forms.Form):
    """Supervisor bulk-approves multiple pending entries."""
    entry_ids = forms.CharField(widget=forms.HiddenInput)

    def clean_entry_ids(self):
        raw = self.cleaned_data.get('entry_ids', '')
        try:
            ids = [int(x) for x in raw.split(',') if x.strip()]
        except ValueError:
            raise forms.ValidationError("Invalid entry selection.")
        if not ids:
            raise forms.ValidationError("No entries selected.")
        return ids


class WeeklyReportForm(forms.ModelForm):
    """Student submits a weekly report."""

    class Meta:
        model  = WeeklyReport
        fields = ['week_start', 'week_end', 'summary',
                  'challenges_faced', 'next_week_plan']
        widgets = {
            'week_start':        forms.DateInput(attrs={'type': 'date'}),
            'week_end':          forms.DateInput(attrs={'type': 'date'}),
            'summary':           forms.Textarea(attrs={'rows': 5,
                'placeholder': 'Summarise what you accomplished this week...'}),
            'challenges_faced':  forms.Textarea(attrs={'rows': 3,
                'placeholder': 'What difficulties did you face, and how did you address them?'}),
            'next_week_plan':    forms.Textarea(attrs={'rows': 3,
                'placeholder': 'What are your goals and plans for next week?'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('week_start')
        end   = cleaned.get('week_end')
        if start and end:
            if end <= start:
                self.add_error('week_end', 'Week end must be after week start.')
            from datetime import timedelta
            if start and end and (end - start).days > 7:
                self.add_error('week_end', 'Week range cannot exceed 7 days.')
        return cleaned


class LogFilterForm(forms.Form):
    """Student/supervisor filter bar for logbook list."""
    status = forms.ChoiceField(
        choices=[('', 'All Statuses'),
                 ('pending', 'Pending'),
                 ('approved', 'Approved'),
                 ('rejected', 'Rejected')],
        required=False,
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='From',
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='To',
    )
