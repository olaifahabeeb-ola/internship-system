from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, DEPARTMENT_CHOICES, LEVEL_CHOICES, FACULTY_CHOICES

STUDENT_DEPT_CHOICES = [c for c in DEPARTMENT_CHOICES if c[0] != 'All Departments']

PROGRAMME_CHOICES_FORM = [
    ('', '— Select programme —'),
    ('ND',  'ND (National Diploma)'),
    ('HND', 'HND (Higher National Diploma)'),
]

LEVEL_CHOICES_FORM = [
    ('', '— Select level —'),
    ('ND1',  'ND 1'),
    ('ND2',  'ND 2'),
    ('HND1', 'HND 1'),
    ('HND2', 'HND 2'),
]


class RegistrationForm(UserCreationForm):
    """
    Student, Supervisor, and Coordinator each get their OWN department
    dropdown (student_department / supervisor_department /
    coordinator_department) so all three can safely coexist in the
    same HTML form — only one shows at a time via JS, but all three
    live in the DOM under different names, so submitting one role
    never collides with another.

    supervisor_department and coordinator_department are deliberately
    excluded from Meta.fields and copied across manually in
    _post_clean()/save() — see the model-level guardrail in
    CustomUser.clean() for why this matters.
    """
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES, required=True)

    email      = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name  = forms.CharField(max_length=50, required=True)
    phone      = forms.CharField(max_length=20, required=False)

    # ── Student-only fields ─────────────────────────────────────
    matric_number      = forms.CharField(max_length=50, required=False)
    student_department = forms.ChoiceField(
        choices=[('', '— Select department —')] + STUDENT_DEPT_CHOICES,
        required=False,
        label='Department',
    )
    programme        = forms.ChoiceField(choices=PROGRAMME_CHOICES_FORM, required=False)
    level            = forms.ChoiceField(choices=LEVEL_CHOICES_FORM, required=False)
    academic_session = forms.CharField(
        max_length=20, required=False, initial='2024/2025',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 2024/2025'}),
    )

    # ── Supervisor-only fields ──────────────────────────────────
    company_name    = forms.CharField(max_length=150, required=False)
    company_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}), required=False
    )
    job_title              = forms.CharField(max_length=100, required=False)
    supervisor_department  = forms.ChoiceField(
        choices=[('', '— Select department —')] + FACULTY_CHOICES,
        required=False,
        label='Department',
        help_text=(
            "Every placement you post will automatically target this "
            "department — it cannot be changed per-posting."
        ),
    )

    # ── Coordinator-only fields ─────────────────────────────────
    staff_id               = forms.CharField(max_length=20, required=False)
    coordinator_department = forms.ChoiceField(
        choices=[('', '— Select department —')] + FACULTY_CHOICES,
        required=False,
        label='Department / Faculty',
        help_text=(
            "This determines which students you will manage — "
            "make sure it matches your department's student list exactly."
        ),
    )

    class Meta:
        model  = CustomUser
        # 'department', 'faculty', and 'supervisor_department' (the
        # real model columns) are deliberately NOT listed here — 
        # they're set manually in _post_clean()/save() from
        # student_department / coordinator_department /
        # supervisor_department, so Django never auto-generates a
        # clashing form field.
        fields = [
            'username', 'first_name', 'last_name', 'email', 'role', 'phone',
            'matric_number', 'programme', 'level', 'academic_session',
            'company_name', 'company_address', 'job_title',
            'staff_id',
            'password1', 'password2',
        ]

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')

        if role == 'student':
            if not cleaned.get('matric_number'):
                self.add_error('matric_number', 'Matric number is required.')
            if not cleaned.get('student_department'):
                self.add_error('student_department', 'Department is required.')
            if not cleaned.get('programme'):
                self.add_error('programme', 'Programme (ND/HND) is required.')
            if not cleaned.get('level'):
                self.add_error('level', 'Level is required.')

        if role == 'supervisor':
            if not cleaned.get('company_name'):
                self.add_error('company_name', 'Company name is required.')
            if not cleaned.get('supervisor_department'):
                self.add_error('supervisor_department', 'Department is required.')

        if role == 'coordinator':
            if not cleaned.get('staff_id'):
                self.add_error('staff_id', 'Staff ID is required.')
            if not cleaned.get('coordinator_department'):
                self.add_error(
                    'coordinator_department',
                    'Department is required — this determines which '
                    'students you will manage.'
                )

        return cleaned

    def _post_clean(self):
        role = self.cleaned_data.get('role') if self.cleaned_data else None
        if role == 'student':
            self.instance.department = self.cleaned_data.get('student_department', '') or ''
        elif role == 'coordinator':
            self.instance.faculty = self.cleaned_data.get('coordinator_department', '') or ''
        elif role == 'supervisor':
            self.instance.supervisor_department = self.cleaned_data.get('supervisor_department', '') or ''

        try:
            super()._post_clean()
        except ValueError:
            pass

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data.get('role')

        if role == 'student':
            user.department = self.cleaned_data.get('student_department', '')
        elif role == 'coordinator':
            user.faculty = self.cleaned_data.get('coordinator_department', '')
        elif role == 'supervisor':
            user.supervisor_department = self.cleaned_data.get('supervisor_department', '')

        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Password'
        })
    )


class ProfileUpdateForm(forms.ModelForm):
    """
    A logged-in user only ever edits fields for THEIR OWN role, so
    there's no collision risk here — department, faculty, and
    supervisor_department map straight to model fields of the same
    name, no renaming needed.
    """
    department = forms.ChoiceField(
        choices=[('', '— Select department —')] + STUDENT_DEPT_CHOICES,
        required=False,
    )
    programme = forms.ChoiceField(choices=PROGRAMME_CHOICES_FORM, required=False)
    level     = forms.ChoiceField(choices=LEVEL_CHOICES_FORM, required=False)
    faculty   = forms.ChoiceField(
        choices=[('', '— Select department —')] + FACULTY_CHOICES,
        required=False,
    )
    supervisor_department = forms.ChoiceField(
        choices=[('', '— Select department —')] + FACULTY_CHOICES,
        required=False,
        label='Department (for posting placements)',
    )

    class Meta:
        model  = CustomUser
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'matric_number', 'department', 'programme', 'level', 'academic_session',
            'company_name', 'company_address', 'job_title', 'supervisor_department',
            'staff_id', 'faculty',
        ]