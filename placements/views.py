from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count

from accounts.decorators import coordinator_required, student_required, supervisor_required
from accounts.models import CustomUser, DEPARTMENT_CHOICES
from .models import Placement, Application
from .forms import (
    PlacementForm, ApplicationForm, ReviewApplicationForm,
    SupervisorPlacementForm, PlacementApprovalForm,
)


# ── Helper ────────────────────────────────────────────────────────────────────

def _coord_dept(coordinator):
    """Returns the coordinator's department string."""
    return (coordinator.department or coordinator.faculty or '').strip()


# ══════════════════════════════════════════════════════════════════
#  SHARED / STUDENT VIEWS
# ══════════════════════════════════════════════════════════════════

@login_required
def placement_list(request):
    """
    Students browse placements filtered STRICTLY by their own
    department — no 'All Departments' wildcard. Only approved, open
    placements are ever shown. If a student has no department set,
    they see NOTHING rather than every placement.
    Coordinators are redirected to their management list.
    """
    if request.user.is_coordinator:
        return redirect('placements:coordinator_list')

    placements = Placement.objects.filter(
        status='open', approval_status='approved'
    ).order_by('-created_at')
    dept_warning = None

    if request.user.is_student:
        student = request.user
        if not student.has_department:
            dept_warning = (
                "Please update your profile with your department "
                "to see placements."
            )
            placements = placements.none()
        else:
            placements = placements.filter(target_department=student.department)
            if student.programme:
                placements = placements.filter(
                    Q(target_programme='Both') |
                    Q(target_programme=student.programme)
                )
            if student.level:
                placements = placements.filter(
                    Q(target_level='All Levels') |
                    Q(target_level=student.level)
                )

    q = request.GET.get('q', '').strip()
    if q:
        placements = placements.filter(
            Q(title__icontains=q) |
            Q(company_name__icontains=q) |
            Q(required_skills__icontains=q) |
            Q(location__icontains=q)
        )

    applied_ids = set()
    if request.user.is_student:
        applied_ids = set(
            Application.objects
            .filter(student=request.user)
            .values_list('placement_id', flat=True)
        )

    context = {
        'placements':   placements,
        'applied_ids':  applied_ids,
        'query':        q,
        'dept_warning': dept_warning,
    }
    return render(request, 'placements/list.html', context)


@login_required
def placement_detail(request, pk):
    placement = get_object_or_404(Placement, pk=pk)

    if request.user.is_student and not placement.is_visible_to_student(request.user):
        messages.error(request, "That placement is not available to you.")
        return redirect('placements:list')

    user_application = None
    if request.user.is_student:
        user_application = Application.objects.filter(
            student=request.user, placement=placement
        ).first()
    context = {'placement': placement, 'user_application': user_application}
    return render(request, 'placements/detail.html', context)


# ══════════════════════════════════════════════════════════════════
#  STUDENT VIEWS
# ══════════════════════════════════════════════════════════════════

@student_required
def apply(request, pk):
    placement = get_object_or_404(
        Placement, pk=pk, status='open', approval_status='approved'
    )

    if not placement.is_visible_to_student(request.user):
        messages.error(
            request,
            "This placement is not available to students in your department."
        )
        return redirect('placements:list')

    if Application.objects.filter(
            student=request.user, placement=placement).exists():
        messages.warning(request, "You have already applied to this placement.")
        return redirect('placements:detail', pk=pk)

    if Application.objects.filter(
            student=request.user, status='accepted').exists():
        messages.error(
            request,
            "You have already been accepted for a placement."
        )
        return redirect('placements:my_applications')

    form = ApplicationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        app = form.save(commit=False)
        app.student   = request.user
        app.placement = placement
        app.save()
        messages.success(
            request,
            f'Application submitted for "{placement.title}"! '
            'You will be notified once it is reviewed.'
        )
        return redirect('placements:my_applications')

    context = {'form': form, 'placement': placement}
    return render(request, 'placements/apply.html', context)


@student_required
def my_applications(request):
    applications = (
        Application.objects
        .filter(student=request.user)
        .select_related('placement', 'reviewed_by')
        .order_by('-applied_at')
    )
    counts = {
        'pending':  applications.filter(status='pending').count(),
        'accepted': applications.filter(status='accepted').count(),
        'rejected': applications.filter(status='rejected').count(),
    }
    context = {'applications': applications, 'counts': counts}
    return render(request, 'placements/my_applications.html', context)


# ══════════════════════════════════════════════════════════════════
#  SUPERVISOR VIEWS
# ══════════════════════════════════════════════════════════════════

@supervisor_required
def supervisor_create_placement(request):
    """
    A supervisor submits a placement vacancy for their own company.
    Starts as approval_status='pending' — invisible to students until
    a coordinator approves it. target_department is locked to the
    supervisor's own registered department.
    """
    supervisor = request.user

    form = SupervisorPlacementForm(request.POST or None, supervisor=supervisor)
    if request.method == 'POST' and form.is_valid():
        placement = form.save(commit=False)
        placement.company_name        = supervisor.company_name
        placement.assigned_supervisor = supervisor
        placement.submitted_by        = supervisor
        placement.approval_status     = 'pending'
        placement.status              = 'open'

        sv_dept = (supervisor.supervisor_department or '').strip()
        if sv_dept:
            placement.target_department = sv_dept

        placement.save()
        messages.success(
            request,
            f'"{placement.title}" submitted for review. '
            'It will appear to students once a coordinator approves it.'
        )
        return redirect('placements:supervisor_my_placements')

    context = {'form': form}
    return render(request, 'placements/supervisor_placement_form.html', context)


@supervisor_required
def supervisor_my_placements(request):
    """All placements this supervisor has submitted, with their current approval status."""
    supervisor = request.user
    placements = (
        Placement.objects
        .filter(submitted_by=supervisor)
        .order_by('-created_at')
    )
    counts = {
        'pending':  placements.filter(approval_status='pending').count(),
        'approved': placements.filter(approval_status='approved').count(),
        'rejected': placements.filter(approval_status='rejected').count(),
    }
    context = {'placements': placements, 'counts': counts}
    return render(request, 'placements/supervisor_my_placements.html', context)


# ══════════════════════════════════════════════════════════════════
#  COORDINATOR VIEWS
# ══════════════════════════════════════════════════════════════════

@coordinator_required
def coordinator_list(request):
    coord = request.user
    placements = (
        Placement.objects
        .filter(Q(created_by=coord) | Q(posted_by=coord))
        .annotate(
            app_count          = Count('applications'),
            annotated_accepted = Count('applications',
                filter=Q(applications__status='accepted')),
            annotated_pending  = Count('applications',
                filter=Q(applications__status='pending')),
        )
        .order_by('-created_at')
    )
    stats = {
        'total':        placements.count(),
        'open':         placements.filter(status='open').count(),
        'closed':       placements.filter(status='closed').count(),
        'total_apps':   Application.objects.filter(
                            placement__posted_by=coord).count(),
        'pending_apps': Application.objects.filter(
                            placement__posted_by=coord,
                            status='pending').count(),
    }
    context = {'placements': placements, 'stats': stats}
    return render(request, 'placements/coordinator_placement_list.html', context)


@coordinator_required
def placement_create(request):
    """
    Coordinators no longer create placements directly. Every placement
    must originate from a supervisor's own submission
    (supervisor_create_placement) so that company_name and
    assigned_supervisor are always correct by construction — this is
    the fix for the exact mismatch risk (a coordinator manually
    pairing a placement with the wrong company/supervisor) that this
    whole approval workflow exists to prevent.

    This view is kept — not deleted — purely so any existing
    link/bookmark pointing at 'placements:create' redirects gracefully
    with an explanation instead of breaking with a 404/NoReverseMatch.
    """
    messages.info(
        request,
        "Coordinators can no longer post placements directly. "
        "Placements are submitted by supervisors and appear here for your review and approval."
    )
    return redirect('placements:coordinator_pending_placements')


@coordinator_required
def placement_edit(request, pk):
    """
    Coordinators can adjust a placement's operational details after it
    has been approved — but company_name and assigned_supervisor are
    permanently locked (excluded entirely from PlacementForm).
    """
    coord = request.user
    placement = get_object_or_404(Placement, pk=pk)
    if not (placement.created_by_id == coord.pk or placement.posted_by_id == coord.pk):
        messages.error(request, "You do not have permission to edit that placement.")
        return redirect('placements:coordinator_list')
    form = PlacementForm(
        request.POST or None,
        instance=placement,
        coordinator=coord,
    )
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        dept = _coord_dept(coord)
        if dept:
            updated.target_department = dept
        updated.save()
        messages.success(request, f'Placement "{placement.title}" updated.')
        return redirect('placements:coordinator_list')
    context = {'form': form, 'action': 'Edit', 'placement': placement,
               'dept': _coord_dept(coord)}
    return render(request, 'placements/coordinator_placement_form.html', context)


@coordinator_required
def placement_close(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    if not (placement.created_by_id == request.user.pk or placement.posted_by_id == request.user.pk):
        messages.error(request, "You do not have permission to change that placement.")
        return redirect('placements:coordinator_list')
    if request.method == 'POST':
        if placement.status == 'open':
            placement.status = 'closed'
            messages.info(request, f'"{placement.title}" closed.')
        else:
            placement.status = 'open'
            messages.info(request, f'"{placement.title}" re-opened.')
        placement.save()
    return redirect('placements:coordinator_list')


@coordinator_required
def coordinator_pending_placements(request):
    """
    Placement vacancies submitted by supervisors, awaiting this
    coordinator's approval. Scoped to the coordinator's own department.
    """
    coord = request.user
    dept  = _coord_dept(coord)

    if dept:
        pending = Placement.objects.filter(
            approval_status='pending', target_department=dept
        ).order_by('-created_at')
    else:
        pending = Placement.objects.none()

    context = {
        'pending_placements': pending,
        'dept': dept or 'your department',
    }
    return render(request, 'placements/coordinator_pending_placements.html', context)


@coordinator_required
def review_placement(request, pk):
    """
    Coordinator approves or rejects a placement vacancy submitted by
    a supervisor. Only the coordinator whose department matches the
    placement's target_department may act on it.
    """
    coord = request.user
    dept  = _coord_dept(coord)
    placement = get_object_or_404(Placement, pk=pk, approval_status='pending')

    if not dept or placement.target_department != dept:
        messages.error(
            request,
            "You do not have permission to review that placement submission."
        )
        return redirect('placements:coordinator_pending_placements')

    form = PlacementApprovalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        decision = form.cleaned_data['decision']
        notes    = form.cleaned_data['approval_notes']

        if decision == 'approved':
            placement.approve(coord, notes)
            messages.success(
                request,
                f'"{placement.title}" at {placement.company_name} has been approved '
                'and is now visible to students.'
            )
        else:
            placement.reject(coord, notes)
            messages.info(
                request,
                f'"{placement.title}" at {placement.company_name} has been rejected.'
            )
        return redirect('placements:coordinator_pending_placements')

    context = {
        'placement': placement,
        'form':      form,
    }
    return render(request, 'placements/review_placement.html', context)


@coordinator_required
def coordinator_application_list(request, pk):
    """
    Applications for a specific placement posted by this coordinator.
    Only shows students from this coordinator's department.
    """
    coord     = request.user
    dept      = _coord_dept(coord)
    placement = get_object_or_404(Placement, pk=pk)
    if not (placement.created_by_id == coord.pk or placement.posted_by_id == coord.pk):
        messages.error(request, "You do not have permission to view that placement.")
        return redirect('placements:coordinator_list')

    applications = (
        placement.applications
        .select_related('student', 'reviewed_by')
        .order_by('status', '-applied_at')
    )

    if dept:
        applications = applications.filter(student__department=dept)

    counts = {
        'total':    applications.count(),
        'pending':  applications.filter(status='pending').count(),
        'accepted': applications.filter(status='accepted').count(),
        'rejected': applications.filter(status='rejected').count(),
    }
    context = {
        'placement':    placement,
        'applications': applications,
        'counts':       counts,
    }
    return render(
        request, 'placements/coordinator_application_list.html', context
    )


@coordinator_required
def review_application(request, pk):
    coord = request.user
    application = get_object_or_404(
        Application.objects.select_related('student', 'placement'),
        pk=pk,
        placement__posted_by=coord,
    )

    slot_warning = None
    if application.status == 'pending' and application.placement.is_full:
        slot_warning = (
            f'Warning: "{application.placement.title}" has no remaining slots. '
            'You can still accept this student if you wish.'
        )

    form = ReviewApplicationForm(request.POST or None, application=application)

    if request.method == 'POST' and form.is_valid():
        decision   = form.cleaned_data['decision']
        notes      = form.cleaned_data['review_notes']
        supervisor = form.cleaned_data.get('supervisor')

        application.mark_reviewed(coord, decision, notes)

        closed_count = 0
        if decision == 'accepted':
            if supervisor:
                application.supervisor = supervisor
                application.save(update_fields=['supervisor'])

            other_pending = Application.objects.filter(
                student=application.student,
                status='pending',
            ).exclude(pk=application.pk)

            closed_count = other_pending.count()
            for other in other_pending:
                other.mark_reviewed(
                    coord,
                    'rejected',
                    f'Auto-closed — placed at {application.placement.company_name}',
                )

        verb = 'accepted' if decision == 'accepted' else 'rejected'
        messages.success(
            request,
            f"{application.student.get_full_name()}'s application has been {verb}."
        )
        if closed_count:
            messages.info(
                request,
                f"{closed_count} other pending application(s) for "
                f"{application.student.get_full_name()} were automatically closed."
            )
        return redirect('placements:coordinator_app_list',
                        pk=application.placement.pk)

    context = {
        'application':            application,
        'form':                   form,
        'slot_warning':           slot_warning,
        'supervisor_locked':      form.supervisor_locked,
        'no_matching_supervisor': form.no_matching_supervisor,
        'company_name':           application.placement.company_name,
    }
    return render(request, 'placements/review_application.html', context)


@coordinator_required
def supervised_students(request):
    """Only students placed through this coordinator's placements."""
    coord = request.user
    applications = (
        Application.objects
        .filter(placement__posted_by=coord, status='accepted')
        .select_related('student', 'placement', 'supervisor')
        .order_by('placement__title', 'student__last_name')
    )
    context = {'applications': applications}
    return render(request, 'placements/supervised_students.html', context)


@coordinator_required
def all_applications(request):
    """All applications for this coordinator's placements only."""
    coord = request.user
    dept  = _coord_dept(coord)

    applications = (
        Application.objects
        .filter(placement__posted_by=coord)
        .select_related('student', 'placement', 'reviewed_by')
        .order_by('-applied_at')
    )

    if dept:
        applications = applications.filter(student__department=dept)

    context = {'applications': applications}
    return render(request, 'placements/all_applications.html', context)