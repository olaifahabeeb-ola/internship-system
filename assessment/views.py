from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.utils import timezone
import json

from accounts.decorators import (
    supervisor_required, student_required, coordinator_required,
)
from django.utils import timezone
import json

from accounts.decorators import (
    supervisor_required, student_required, coordinator_required
)
from placements.models import Application
from .models import Assessment, AssessmentCriteria, AssessmentScore, AssessmentSummary
from .forms import AssessmentSummaryForm, CoordinatorFilterForm


# ══════════════════════════════════════════════════════════════════
#  SUPERVISOR VIEWS
# ══════════════════════════════════════════════════════════════════

@supervisor_required
def supervisor_dashboard(request):
    """
    Lists all students assigned to this supervisor with assessment status
    for mid-term and final.
    """
    supervised = (
        Application.objects
        .filter(supervisor=request.user, status='accepted')
        .select_related('student', 'placement')
        .prefetch_related('assessments')
    )

    # Build per-student status map
    student_data = []
    for app in supervised:
        assessments = {a.assessment_type: a for a in app.assessments.all()}
        student_data.append({
            'application': app,
            'mid_term':    assessments.get('mid_term'),
            'final':       assessments.get('final'),
        })

    pending_mid   = sum(1 for d in student_data if not d['mid_term'])
    pending_final = sum(1 for d in student_data if not d['final'])
    completed     = sum(
        1 for d in student_data
        if d['mid_term'] and d['mid_term'].is_submitted
        and d['final']   and d['final'].is_submitted
    )

    context = {
        'student_data':  student_data,
        'pending_mid':   pending_mid,
        'pending_final': pending_final,
        'completed':     completed,
    }
    return render(request, 'assessment/supervisor_dashboard.html', context)


@supervisor_required
def create_assessment(request, app_pk, assessment_type):
    """
    GET  → render blank form (or pre-fill draft).
    POST → save draft or submit final assessment.
    assessment_type is 'mid_term' or 'final'.
    """
    if assessment_type not in ('mid_term', 'final'):
        messages.error(request, "Invalid assessment type.")
        return redirect('assessment:supervisor_dashboard')

    application = get_object_or_404(
        Application,
        pk=app_pk,
        supervisor=request.user,
        status='accepted',
    )

    # Get or create the Assessment header
    assessment, created = Assessment.objects.get_or_create(
        application=application,
        assessment_type=assessment_type,
        defaults={'supervisor': request.user},
    )

    # get_or_create() only applies `defaults` on the FIRST creation —
    # if a draft already exists and the application's supervisor was
    # later reassigned (e.g. fixing a mismatched placement), the
    # existing assessment would otherwise stay locked to whoever
    # started it, permanently unreachable by whoever is actually
    # supervising the student now. Since this view is already gated
    # to application.supervisor == request.user above, keep the
    # assessment's own supervisor field in sync with that.
    if not created and assessment.supervisor_id != request.user.pk:
        assessment.supervisor = request.user
        assessment.save(update_fields=['supervisor'])

    # Block editing a submitted assessment
    if assessment.is_submitted:
        messages.info(request, "This assessment has already been submitted.")
        return redirect('assessment:detail', pk=assessment.pk)

    criteria = AssessmentCriteria.objects.filter(is_active=True).order_by('order')

    # Build or fetch score rows
    existing_scores = {
        s.criterion_id: s
        for s in assessment.scores.select_related('criterion')
    }

    # Get or create AssessmentSummary
    summary, _ = AssessmentSummary.objects.get_or_create(assessment=assessment)

    if request.method == 'POST':
        action = request.POST.get('action', 'draft')  # 'draft' or 'submit'
        errors = []

        # ── Save scores ──────────────────────────────────────────
        for criterion in criteria:
            raw = request.POST.get(f'score_{criterion.pk}', '').strip()
            comment = request.POST.get(f'comment_{criterion.pk}', '').strip()

            if action == 'submit' and not raw:
                errors.append(f'Score required for "{criterion.name}".')
                continue

            if raw:
                try:
                    score_val = int(raw)
                    if score_val < 0 or score_val > criterion.max_score:
                        errors.append(
                            f'"{criterion.name}" must be 0–{criterion.max_score}.'
                        )
                        continue
                except ValueError:
                    errors.append(f'Invalid score for "{criterion.name}".')
                    continue

                score_obj = existing_scores.get(criterion.pk)
                if score_obj:
                    score_obj.score   = score_val
                    score_obj.comment = comment
                    score_obj.save()
                else:
                    score_obj = AssessmentScore.objects.create(
                        assessment=assessment,
                        criterion=criterion,
                        score=score_val,
                        comment=comment,
                    )
                    existing_scores[criterion.pk] = score_obj

        # ── Save summary ─────────────────────────────────────────
        summary_form = AssessmentSummaryForm(request.POST, instance=summary)
        if summary_form.is_valid():
            summary_form.save()
        else:
            if action == 'submit':
                errors.append("Please complete the Overall Feedback section.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            assessment.recalculate_totals()

            if action == 'submit':
                assessment.status = 'submitted'
                assessment.save(update_fields=['status'])
                messages.success(
                    request,
                    f"{assessment.get_assessment_type_display()} for "
                    f"{application.student.get_full_name()} submitted successfully."
                )
                return redirect('assessment:detail', pk=assessment.pk)
            else:
                assessment.save(update_fields=['last_modified'])
                messages.success(request, "Draft saved.")
                return redirect('assessment:create',
                                app_pk=app_pk,
                                assessment_type=assessment_type)

    # ── GET: build form data ──────────────────────────────────────
    summary_form  = AssessmentSummaryForm(instance=summary)
    score_data    = []
    running_total = 0
    for criterion in criteria:
        s = existing_scores.get(criterion.pk)
        score_data.append({
            'criterion': criterion,
            'score':     s.score   if s else '',
            'comment':   s.comment if s else '',
        })
        if s:
            running_total += s.score

    max_possible = sum(c.max_score for c in criteria)

    context = {
        'assessment':     assessment,
        'application':    application,
        'score_data':     score_data,
        'summary_form':   summary_form,
        'running_total':  running_total,
        'max_possible':   max_possible,
        'criteria_json':  json.dumps([
            {'pk': c.pk, 'max': c.max_score} for c in criteria
        ]),
    }
    return render(request, 'assessment/create_assessment.html', context)
@login_required
def assessment_detail(request, pk):
    """
    Shared read-only view — supervisor, student (own), coordinator.
    """
    assessment = get_object_or_404(
        Assessment.objects.select_related(
            'application__student',
            'application__placement',
            'supervisor',
        ).prefetch_related('scores__criterion'),
        pk=pk,
    )

    # Permission checks
    user = request.user
    if user.is_student and assessment.student != user:
        messages.error(request, "You can only view your own assessments.")
        return redirect('accounts:dashboard')
    if user.is_supervisor and assessment.supervisor != user:
        messages.error(request, "You can only view assessments you created.")
        return redirect('accounts:dashboard')
    if user.is_coordinator:
        if assessment.placement.posted_by != user:
            messages.error(request, "You can only view assessments for your placements.")
            return redirect('accounts:dashboard')

    summary = getattr(assessment, 'summary', None)
    scores  = assessment.scores.select_related('criterion').order_by('criterion__order')

    # Group by category
    soft_scores = [s for s in scores if s.criterion.category == 'soft_skills']
    tech_scores = [s for s in scores if s.criterion.category == 'technical_skills']

    context = {
        'assessment':   assessment,
        'summary':      summary,
        'soft_scores':  soft_scores,
        'tech_scores':  tech_scores,
        'can_edit':     (
            user.is_supervisor
            and assessment.supervisor == user
            and not assessment.is_submitted
        ),
    }
    return render(request, 'assessment/assessment_detail.html', context)


# ══════════════════════════════════════════════════════════════════
#  STUDENT VIEWS
# ══════════════════════════════════════════════════════════════════

@student_required
def student_assessments(request):
    """Student views their mid-term and final assessments."""
    application = (
        Application.objects
        .filter(student=request.user, status='accepted')
        .select_related('placement', 'supervisor')
        .first()
    )

    mid_term = None
    final    = None
    if application:
        assessments = Assessment.objects.filter(
            application=application
        ).prefetch_related('scores__criterion')
        for a in assessments:
            if a.assessment_type == 'mid_term':
                mid_term = a
            else:
                final = a

    context = {
        'application': application,
        'mid_term':    mid_term,
        'final':       final,
    }
    return render(request, 'assessment/student_assessments.html', context)


@student_required
def acknowledge_assessment(request, pk):
    """Student acknowledges having read their assessment."""
    assessment = get_object_or_404(Assessment, pk=pk, status='submitted')

    if assessment.student != request.user:
        messages.error(request, "You can only acknowledge your own assessments.")
        return redirect('assessment:student_assessments')

    summary = getattr(assessment, 'summary', None)
    if summary and not summary.student_acknowledged:
        summary.acknowledge()
        messages.success(request, "Assessment acknowledged. Thank you.")
    elif summary and summary.student_acknowledged:
        messages.info(request, "You have already acknowledged this assessment.")

    return redirect('assessment:student_assessments')


# ══════════════════════════════════════════════════════════════════
#  COORDINATOR VIEWS
# ══════════════════════════════════════════════════════════════════

@coordinator_required
def coordinator_assessment_list(request):
    """Coordinator sees all assessments for their placements with filters."""
    dept = (request.user.department or request.user.faculty or '').strip()
    assessments = (
        Assessment.objects
        .filter(application__placement__posted_by=request.user)
        .select_related(
            'application__student',
            'application__placement',
            'supervisor',
        )
        .prefetch_related('summary')
        .order_by('-submission_date')
    )

    form = CoordinatorFilterForm(request.GET or None)
    if dept:
        assessments = assessments.filter(application__student__department=dept)

    if form.is_valid():
        name = form.cleaned_data.get('student_name')
        company = form.cleaned_data.get('company')
        a_type  = form.cleaned_data.get('assessment_type')
        status  = form.cleaned_data.get('status')
        d_from  = form.cleaned_data.get('date_from')
        d_to    = form.cleaned_data.get('date_to')

        if name:
            assessments = assessments.filter(
                Q(application__student__first_name__icontains=name) |
                Q(application__student__last_name__icontains=name)
            )
        if company:
            assessments = assessments.filter(
                application__placement__company_name__icontains=company
            )
        if a_type:
            assessments = assessments.filter(assessment_type=a_type)
        if status:
            assessments = assessments.filter(status=status)
        if d_from:
            assessments = assessments.filter(submission_date__date__gte=d_from)
        if d_to:
            assessments = assessments.filter(submission_date__date__lte=d_to)

    # Quick stats
    submitted = assessments.filter(status='submitted')
    avg_score = submitted.aggregate(avg=Avg('total_score'))['avg'] or 0

    context = {
        'assessments': assessments,
        'form':        form,
        'total':       assessments.count(),
        'submitted':   submitted.count(),
        'avg_score':   round(float(avg_score), 1),
    }
    return render(request, 'assessment/coordinator_assessment_list.html', context)


@coordinator_required
def coordinator_stats(request):
    """Coordinator statistics page with Chart.js visuals."""
    from placements.models import Application as App

    dept = (request.user.department or request.user.faculty or '').strip()
    all_submitted = Assessment.objects.filter(
        application__placement__posted_by=request.user,
        status='submitted',
    ).prefetch_related('scores__criterion', 'summary')
    if dept:
        all_submitted = all_submitted.filter(application__student__department=dept)

    # ── Average score per criterion ───────────────────────────────
    criteria     = AssessmentCriteria.objects.filter(is_active=True).order_by('order')
    criteria_avg = []
    for c in criteria:
        avg = (
            AssessmentScore.objects
            .filter(
                assessment__application__placement__posted_by=request.user,
                assessment__status='submitted',
                criterion=c,
            )
            .aggregate(avg=Avg('score'))['avg']
        )
        criteria_avg.append({
            'name': c.name,
            'avg':  round(float(avg or 0), 2),
            'max':  c.max_score,
        })

    # ── Recommendation distribution ───────────────────────────────
    rec_labels = ['Excellent', 'Good', 'Satisfactory', 'Needs Improvement', 'Unsatisfactory']
    rec_keys   = ['excellent', 'good', 'satisfactory', 'needs_improvement', 'unsatisfactory']
    rec_data   = [
        AssessmentSummary.objects.filter(
            assessment__application__placement__posted_by=request.user,
            assessment__status='submitted',
            recommendation=key,
        ).count()
        for key in rec_keys
    ]

    # ── Missing assessments ───────────────────────────────────────
    placed_apps = App.objects.filter(
        placement__posted_by=request.user, status='accepted'
    ).select_related('student', 'placement')
    if dept:
        placed_apps = placed_apps.filter(student__department=dept)

    missing_mid   = []
    missing_final = []
    for app in placed_apps:
        has_mid   = app.assessments.filter(assessment_type='mid_term',  status='submitted').exists()
        has_final = app.assessments.filter(assessment_type='final',     status='submitted').exists()
        if not has_mid:
            missing_mid.append(app)
        if not has_final:
            missing_final.append(app)

    # Overall average
    overall_avg = all_submitted.aggregate(avg=Avg('total_score'))['avg'] or 0

    context = {
        'total_submitted':  all_submitted.count(),
        'overall_avg':      round(float(overall_avg), 1),
        'missing_mid':      missing_mid,
        'missing_final':    missing_final,
        'criteria_avg':     criteria_avg,
        # Chart.js JSON
        'bar_labels':       json.dumps([c['name'] for c in criteria_avg]),
        'bar_data':         json.dumps([c['avg']  for c in criteria_avg]),
        'pie_labels':       json.dumps(rec_labels),
        'pie_data':         json.dumps(rec_data),
        'rec_colours': json.dumps([
            '#198754', '#0d6efd', '#0dcaf0', '#ffc107', '#dc3545'
        ]),
    }
    return render(request, 'assessment/coordinator_stats.html', context)


# ── Stubs to satisfy existing sidebar URL references ─────────────

@supervisor_required
def assess_student(request, app_pk):
    """Redirect shortcut from supervisor dashboard → mid-term by default."""
    return redirect('assessment:create', app_pk=app_pk, assessment_type='mid_term')


@student_required
def my_assessment(request):
    return redirect('assessment:student_assessments')


@supervisor_required
def supervisor_list(request):
    return redirect('assessment:supervisor_dashboard')
