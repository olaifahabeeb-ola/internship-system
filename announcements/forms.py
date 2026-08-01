from django import forms
from accounts.models import CustomUser, DEPARTMENT_CHOICES
from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model  = Announcement
        fields = ['title', 'message', 'target_audience', 'target_department',
                  'specific_user', 'priority', 'is_active']
        widgets = {
            'title':   forms.TextInput(attrs={
                'placeholder': 'Announcement title...'
            }),
            'message': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Write your announcement here...'
            }),
            'target_audience': forms.Select(
                attrs={'id': 'id_target_audience'}
            ),
            'target_department': forms.Select(),
            'specific_user': forms.Select(
                attrs={'id': 'id_specific_user'}
            ),
            'priority': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        coordinator = kwargs.pop('coordinator', None)
        super().__init__(*args, **kwargs)

        all_dept_choices = [
            (d[0], d[1]) for d in DEPARTMENT_CHOICES if d[0] != 'All Departments'
        ]
        valid_depts = dict(all_dept_choices)

        dept = (coordinator.department or coordinator.faculty or '').strip() if coordinator else ''

        # Read by clean() below. See the long comment further down for
        # why this exists separately from the field's own disabled/
        # initial mechanism.
        self.locked_department = None

        if dept and dept in valid_depts:
            # Lock target_department to the coordinator's own department
            # — a coordinator manages exactly one department and must
            # never be able to send an announcement targeting a
            # different one.
            #
            # IMPORTANT: disabled=True + initial=dept, by themselves,
            # do NOT guarantee this locked value ends up in cleaned_data
            # on a form with no bound instance (a fresh "create" form,
            # which is exactly how coordinator_create uses this form).
            # Django resolves a disabled field's value from self.initial
            # FIRST — and for a brand-new ModelForm instance, self.initial
            # already has an entry for target_department (the blank
            # instance's own default), so field.initial set here is
            # never actually consulted. On the CREATE path this would
            # silently resolve to blank instead of `dept`.
            #
            # This form-level lock is still worth keeping — it's the
            # visible UI restriction, and it stops a tampered raw POST
            # value from being accepted. The real source of correctness
            # is self.locked_department (used in clean() below) plus the
            # matching explicit re-assignment in coordinator_create /
            # coordinator_edit in views.py.
            self.fields['target_department'].choices  = [(dept, valid_depts[dept])]
            self.fields['target_department'].initial  = dept
            self.fields['target_department'].disabled = True
            self.fields['target_department'].help_text = (
                f'Locked to your department ({dept}) — '
                'you can only announce to your own students.'
            )
            self.locked_department = dept
        else:
            # No valid department on file for this coordinator (legacy
            # account) — fall back to the full open list rather than
            # blocking announcement creation entirely.
            self.fields['target_department'].choices = (
                [('', '— Select department —')] + all_dept_choices
            )

        self.fields['target_department'].required = False

        # Scope specific_user to:
        # - Students in this coordinator's department
        # - Supervisors of placed students under this coordinator's placements
        if coordinator and dept:
            from placements.models import Application
            from django.db.models import Q

            dept_students = CustomUser.objects.filter(
                role='student', department=dept
            )
            supervisor_ids = Application.objects.filter(
                placement__posted_by=coordinator,
                status='accepted',
                supervisor__isnull=False,
            ).values_list('supervisor_id', flat=True).distinct()
            supervisors = CustomUser.objects.filter(pk__in=supervisor_ids)

            self.fields['specific_user'].queryset = (
                CustomUser.objects.filter(
                    Q(pk__in=dept_students) | Q(pk__in=supervisors)
                ).order_by('role', 'last_name', 'first_name')
            )
        else:
            self.fields['specific_user'].queryset = (
                CustomUser.objects
                .filter(role__in=['student', 'supervisor'])
                .order_by('role', 'last_name', 'first_name')
            )

        self.fields['specific_user'].required    = False
        self.fields['specific_user'].empty_label = '— Select user —'

    def clean(self):
        cleaned    = super().clean()
        audience   = cleaned.get('target_audience')
        user       = cleaned.get('specific_user')
        department = cleaned.get('target_department')

        # If this coordinator is locked to one department, that's the
        # effective department no matter what cleaned_data resolved to
        # — see the note in __init__ on why a disabled field's cleaned
        # value can't be trusted alone on a fresh create form.
        if self.locked_department:
            department = self.locked_department
            cleaned['target_department'] = department

        if audience in ('specific_student', 'specific_supervisor') and not user:
            self.add_error('specific_user',
                           'You must select a specific user for this audience type.')
        if audience == 'specific_department' and not department:
            self.add_error('target_department', 'Please choose the target department.')
        return cleaned