from django import forms
from .models import Assessment, AssessmentScore, AssessmentSummary, AssessmentCriteria


class AssessmentMetaForm(forms.ModelForm):
    """
    Top section of the assessment: student, type selection.
    The supervisor selects which student and which type (mid/final).
    """
    class Meta:
        model  = Assessment
        fields = ['assessment_type']
        widgets = {
            'assessment_type': forms.RadioSelect,
        }


class AssessmentScoreForm(forms.ModelForm):
    """
    One score row per criterion — instantiated as a formset.

    The 0-10 range was hardcoded here on the assumption every
    criterion's max_score is 10 — true only for today's seed data.
    AssessmentCriteria.max_score is a genuinely configurable field, so
    a criterion worth more than 10 could never receive a full score,
    and a criterion worth less than 10 could silently accept an
    inflated one that then feeds straight into
    Assessment.recalculate_totals(). Pass the real criterion in at
    construction time so validation always matches its actual ceiling.
    """
    class Meta:
        model  = AssessmentScore
        fields = ['score', 'comment']
        widgets = {
            'score': forms.NumberInput(attrs={
                'min': 0, 'step': 1,
                'class': 'form-control score-input',
                'style': 'width:80px;',
            }),
            'comment': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Optional comment...',
            }),
        }

    def __init__(self, *args, criterion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.criterion = criterion
        if criterion is not None:
            # Reflect the real ceiling in the HTML widget too, so the
            # number input's spinner/browser validation matches the
            # server-side rule instead of always capping at 10.
            self.fields['score'].widget.attrs['max'] = criterion.max_score

    def clean_score(self):
        score = self.cleaned_data.get('score')
        max_score = self.criterion.max_score if self.criterion else 10
        if score is not None and (score < 0 or score > max_score):
            raise forms.ValidationError(
                f'Score must be between 0 and {max_score} for this criterion.'
            )
        return score


class AssessmentSummaryForm(forms.ModelForm):
    """Overall feedback section at the bottom of the assessment form."""
    class Meta:
        model  = AssessmentSummary
        fields = [
            'overall_comment', 'strengths',
            'areas_for_improvement', 'recommendation',
        ]
        widgets = {
            'overall_comment':       forms.Textarea(attrs={
                'rows': 4,
                'placeholder': "General comments on the intern's performance...",
            }),
            'strengths':             forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'What did the student do particularly well?',
            }),
            'areas_for_improvement': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Where can the student improve?',
            }),
            'recommendation':        forms.Select(attrs={'class': 'form-select'}),
        }


class CoordinatorFilterForm(forms.Form):
    """Filter bar on the coordinator's assessment list page."""
    student_name  = forms.CharField(required=False, label='Student name',
                                    widget=forms.TextInput(attrs={'placeholder': 'Search name...'}))
    company       = forms.CharField(required=False, label='Company',
                                    widget=forms.TextInput(attrs={'placeholder': 'Company...'}))
    assessment_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types'), ('mid_term', 'Mid-Term'), ('final', 'Final')],
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses'), ('draft', 'Draft'), ('submitted', 'Submitted')],
    )
    date_from = forms.DateField(required=False,
                                widget=forms.DateInput(attrs={'type': 'date'}))
    date_to   = forms.DateField(required=False,
                                widget=forms.DateInput(attrs={'type': 'date'}))
