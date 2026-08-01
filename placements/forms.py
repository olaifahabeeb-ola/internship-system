from django import forms
from django.conf import settings
import os
from placements.models import Placement, Application, TARGETABLE_DEPARTMENT_CHOICES
from accounts.models import CustomUser


class PlacementForm(forms.ModelForm):
    """
    Coordinator-facing form — EDIT ONLY. Coordinators can no longer
    create placements from scratch (see placement_create in views.py).
    This form is only ever used to adjust an already-approved
    placement's operational details.

    company_name and assigned_supervisor are DELIBERATELY excluded
    from Meta.fields below — not just disabled, fully omitted. Once a
    supervisor's submission is approved, those two fields are locked
    for good. Allowing a coordinator to change them here would reopen
    the exact mismatch risk (pairing a placement with the wrong
    company/supervisor) this whole approval workflow exists to
    prevent. Omitting a field from a ModelForm means save() never
    touches it — the existing DB value is left completely alone.
    """
    class Meta:
        model  = Placement
        fields = [
            'title', 'description', 'required_skills',
            'location', 'start_date', 'end_date', 'slots_available',
            'target_department',
        ]
        widgets = {
            'start_date':         forms.DateInput(attrs={'type': 'date'}),
            'end_date':           forms.DateInput(attrs={'type': 'date'}),
            'description':        forms.Textarea(attrs={'rows': 4}),
            'required_skills':    forms.TextInput(
                attrs={'placeholder': 'e.g. Python, Excel, Communication'}
            ),
            'target_department':  forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        coordinator = kwargs.pop('coordinator', None)
        super().__init__(*args, **kwargs)

        if coordinator:
            coord_dept  = (getattr(coordinator, 'department', '') or getattr(coordinator, 'faculty', '')).strip()
            valid_depts = dict(TARGETABLE_DEPARTMENT_CHOICES)

            if coord_dept and coord_dept in valid_depts:
                self.fields['target_department'].choices  = [(coord_dept, valid_depts[coord_dept])]
                self.fields['target_department'].initial  = coord_dept
                self.fields['target_department'].disabled = True
                self.fields['target_department'].help_text = (
                    f'Locked to your department ({coord_dept}) — this is who you manage.'
                )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end   = cleaned.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'End date must be after start date.')
        return cleaned


class SupervisorPlacementForm(forms.ModelForm):
    """
    Supervisor-facing form for submitting a placement vacancy at their
    own company. target_department is locked to the supervisor's own
    registered department (CustomUser.supervisor_department) —
    mirroring exactly how PlacementForm locks a coordinator's
    target_department to their own faculty.
    """
    class Meta:
        model  = Placement
        fields = [
            'title', 'description', 'required_skills',
            'location', 'start_date', 'end_date', 'slots_available',
            'target_department',
        ]
        widgets = {
            'start_date':      forms.DateInput(attrs={'type': 'date'}),
            'end_date':        forms.DateInput(attrs={'type': 'date'}),
            'description':     forms.Textarea(attrs={'rows': 4}),
            'required_skills': forms.TextInput(
                attrs={'placeholder': 'e.g. Python, Excel, Communication'}
            ),
        }
        labels = {
            'target_department': 'Which department is this internship for?',
        }

    def __init__(self, *args, **kwargs):
        supervisor = kwargs.pop('supervisor', None)
        super().__init__(*args, **kwargs)

        valid_depts = dict(self.fields['target_department'].choices)
        sv_dept = (getattr(supervisor, 'supervisor_department', '') or '').strip() if supervisor else ''

        if sv_dept and sv_dept in valid_depts:
            # Lock target_department to the supervisor's registered
            # department. disabled=True means Django ignores any
            # tampered POST value and always uses `initial`
            # server-side — this is the actual enforcement, not just
            # a UI nicety.
            self.fields['target_department'].choices  = [(sv_dept, valid_depts[sv_dept])]
            self.fields['target_department'].initial  = sv_dept
            self.fields['target_department'].disabled = True
            self.fields['target_department'].help_text = (
                f'Locked to your registered department ({sv_dept}).'
            )
        else:
            # Legacy account with no department set yet — fall back to
            # a full open dropdown rather than blocking posting
            # entirely. Encourage them to set it via profile.
            self.fields['target_department'].choices = (
                [('', '— Select department —')] +
                list(self.fields['target_department'].choices)
            )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end   = cleaned.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'End date must be after start date.')
        return cleaned

class ApplicationForm(forms.ModelForm):
    class Meta:
        model  = Application
        fields = ['cover_letter', 'cv']
        widgets = {
            'cover_letter': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Explain why you are a good fit...'
            }),
        }

    def clean_cv(self):
        cv = self.cleaned_data.get('cv')
        if not cv:
            return cv
        ext = os.path.splitext(cv.name)[1].lower().lstrip('.')
        allowed = getattr(settings, 'CV_ALLOWED_EXTENSIONS', ['pdf', 'docx'])
        if ext not in allowed:
            raise forms.ValidationError(
                f"Only {', '.join(allowed).upper()} files are allowed."
            )
        max_bytes = getattr(settings, 'CV_MAX_SIZE_BYTES', 2 * 1024 * 1024)
        if cv.size > max_bytes:
            raise forms.ValidationError(
                f"File must not exceed {getattr(settings, 'CV_MAX_SIZE_MB', 2)} MB."
            )
        return cv


class ReviewApplicationForm(forms.Form):
    DECISION_CHOICES = [
        ('accepted', 'Accept'),
        ('rejected', 'Reject'),
    ]
    decision     = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect)
    supervisor   = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        required=False,
        label='Assign Supervisor',
        help_text='Required when accepting this application.',
    )
    review_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional note...'}),
        label='Note to student (optional)',
    )

    def __init__(self, *args, application=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.application = application
        self.supervisor_locked      = False
        self.no_matching_supervisor = False

        if application is None:
            return

        placement = application.placement

        if placement.assigned_supervisor_id:
            self.fields['supervisor'].queryset = CustomUser.objects.filter(
                pk=placement.assigned_supervisor_id, role='supervisor'
            )
            self.fields['supervisor'].initial = placement.assigned_supervisor_id
            self.supervisor_locked = True
        else:
            matches = placement.matching_supervisors()
            self.fields['supervisor'].queryset = matches
            if not matches.exists():
                self.no_matching_supervisor = True

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('decision') == 'accepted' and not cleaned.get('supervisor'):
            self.add_error('supervisor', 'Please assign a supervisor before accepting.')
        return cleaned


class PlacementApprovalForm(forms.Form):
    DECISION_CHOICES = [
        ('approved', 'Approve'),
        ('rejected', 'Reject'),
    ]
    decision       = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect)
    approval_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Optional note for the supervisor (e.g. reason for rejection)...'
        }),
        label='Note to supervisor (optional)',
    )