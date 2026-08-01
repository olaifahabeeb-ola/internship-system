import csv
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Avg, Q

from accounts.decorators import coordinator_required
from accounts.models import CustomUser
from placements.models import Placement, Application
from logbook.models import LogbookEntry
from assessment.models import Assessment, AssessmentSummary


# ── Helpers ───────────────────────────────────────────────────────

def _get_student_report_data(application):
    """Build all data for one student's report. Reused by HTML + CSV views."""
    logs = LogbookEntry.objects.filter(
        application=application
    ).order_by('-date')

    log_stats = {
        'total':    logs.count(),
        'approved': logs.filter(status='approved').count(),
        'rejected': logs.filter(status='rejected').count(),
        'pending':  logs.filter(status='pending').count(),
    }
    if log_stats['total'] > 0:
        log_stats['approval_pct'] = round(
            log_stats['approved'] / log_stats['total'] * 100, 1
        )
    else:
        log_stats['approval_pct'] = 0

    assessments = {
        a.assessment_type: a
        for a in Assessment.objects.filter(
            application=application, status='submitted'
        ).prefetch_related('scores__criterion', 'summary')
    }

    return {
        'application': application,
        'logs':        logs,
        'log_stats':   log_stats,
        'mid_term':    assessments.get('mid_term'),
        'final':       assessments.get('final'),
    }


def _build_aggregate_context(request):
    """
    Builds every stat needed by the aggregate report. Shared by BOTH
    the on-screen view and the print/PDF view, so the two can never
    silently drift apart.
    """
    date_from_raw = request.GET.get('date_from')
    date_to_raw   = request.GET.get('date_to')

    try:
        from datetime import date as date_cls
        date_from = date_cls.fromisoformat(date_from_raw) if date_from_raw else None
        date_to   = date_cls.fromisoformat(date_to_raw)   if date_to_raw   else None
    except (ValueError, TypeError):
        date_from = date_to = None

    # ── Placement stats ───────────────────────────────────────────
    dept = (request.user.department or request.user.faculty or '').strip()
    placements  = Placement.objects.filter(posted_by=request.user)
    placed_apps = Application.objects.filter(
        placement__posted_by=request.user, status='accepted'
    )
    if dept:
        placed_apps = placed_apps.filter(student__department=dept)

    # How many placed students have no supervisor assigned at all —
    # surfaced here so a coordinator can spot this at a glance instead
    # of discovering it one student report at a time.
    placed_apps_no_supervisor = placed_apps.filter(supervisor__isnull=True).count()

    per_company = (
        placed_apps
        .values('placement__company_name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    per_dept = (
        placed_apps
        .values('student__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # ── Logbook stats ─────────────────────────────────────────────
    log_qs = LogbookEntry.objects.filter(
        application__placement__posted_by=request.user
    )
    if date_from: log_qs = log_qs.filter(date__gte=date_from)
    if date_to:   log_qs = log_qs.filter(date__lte=date_to)

    log_stats = {
        'total':           log_qs.count(),
        'approved':        log_qs.filter(status='approved').count(),
        'rejected':        log_qs.filter(status='rejected').count(),
        'pending':         log_qs.filter(status='pending').count(),
        'avg_per_student': 0,
        'approval_pct':    0,
    }
    placed_count = placed_apps.count()
    if placed_count and log_stats['total']:
        log_stats['avg_per_student'] = round(log_stats['total'] / placed_count, 1)
    if log_stats['total']:
        log_stats['approval_pct'] = round(
            log_stats['approved'] / log_stats['total'] * 100, 1
        )

    # ── Assessment stats ──────────────────────────────────────────
    assess_qs = Assessment.objects.filter(
        application__placement__posted_by=request.user,
        status='submitted',
    )
    avg_score  = assess_qs.aggregate(avg=Avg('total_score'))['avg'] or 0
    grade_dist = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    for a in assess_qs:
        grade_dist[a.grade_letter] = grade_dist.get(a.grade_letter, 0) + 1

    return {
        'placements':                placements,
        'placed_apps':               placed_apps,
        'placed_apps_no_supervisor': placed_apps_no_supervisor,
        'per_company':               per_company,
        'per_dept':                  per_dept,
        'log_stats':                 log_stats,
        'avg_score':                 round(float(avg_score), 1),
        'grade_dist':                grade_dist,
        'assess_total':              assess_qs.count(),
        'date_from':                 date_from_raw or '',
        'date_to':                   date_to_raw   or '',
    }

# ── Index ─────────────────────────────────────────────────────────

@coordinator_required
def reports_index(request):
    """Report selection hub."""
    dept = (request.user.department or request.user.faculty or '').strip()
    placed_apps = (
        Application.objects
        .filter(placement__posted_by=request.user, status='accepted')
        .select_related('student', 'placement')
        .order_by('student__last_name')
    )
    if dept:
        placed_apps = placed_apps.filter(student__department=dept)
    context = {'placed_apps': placed_apps}
    return render(request, 'reports/index.html', context)


# ── Individual student report ─────────────────────────────────────

@coordinator_required
def student_report(request, student_id):
    student = get_object_or_404(CustomUser, pk=student_id, role='student')
    application = get_object_or_404(
        Application,
        student=student,
        placement__posted_by=request.user,
        status='accepted',
    )
    data = _get_student_report_data(application)
    data['print_mode'] = False
    return render(request, 'reports/student_report.html', data)


@coordinator_required
def student_report_pdf(request, student_id):
    """Same page but with print_mode=True — JS auto-triggers print dialog."""
    student = get_object_or_404(CustomUser, pk=student_id, role='student')
    application = get_object_or_404(
        Application,
        student=student,
        placement__posted_by=request.user,
        status='accepted',
    )
    data = _get_student_report_data(application)
    data['print_mode'] = True
    return render(request, 'reports/student_report.html', data)


@coordinator_required
def student_report_csv(request, student_id):
    """Download all log entries for one student as a CSV file."""
    student = get_object_or_404(CustomUser, pk=student_id, role='student')
    application = get_object_or_404(
        Application,
        student=student,
        placement__posted_by=request.user,
        status='accepted',
    )
    logs = LogbookEntry.objects.filter(
        application=application
    ).order_by('date')

    filename = f"logbook_{student.username}_{timezone.now().strftime('%Y%m%d')}.csv"
    response  = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Day', 'Activities Performed', 'Skills Gained',
        'Hours Worked', 'Attachment', 'Status', 'Supervisor Comment',
        'Reviewed By', 'Reviewed At',
    ])
    for log in logs:
        writer.writerow([
            log.date.strftime('%Y-%m-%d'),
            log.date.strftime('%A'),
            log.activity_description,
            log.skills_gained,
            log.hours_worked,
            request.build_absolute_uri(log.attachment.url) if log.attachment else '',
            log.get_status_display(),
            log.supervisor_comment,
            log.reviewed_by.get_full_name() if log.reviewed_by else '',
            log.reviewed_at.strftime('%Y-%m-%d %H:%M') if log.reviewed_at else '',
        ])
    return response


# ── Aggregate report ──────────────────────────────────────────────

@coordinator_required
def aggregate_report(request):
    context = _build_aggregate_context(request)
    context['print_mode'] = False
    return render(request, 'reports/aggregate_report.html', context)


@coordinator_required
def aggregate_report_pdf(request):
    """Same report, print_mode=True — the template's JS auto-triggers print."""
    context = _build_aggregate_context(request)
    context['print_mode'] = True
    return render(request, 'reports/aggregate_report.html', context)


@coordinator_required
def aggregate_report_csv(request):
    """Export placed student summary as CSV."""
    dept = (request.user.department or request.user.faculty or '').strip()
    placed_apps = (
        Application.objects
        .filter(placement__posted_by=request.user, status='accepted')
        .select_related('student', 'placement', 'supervisor')
        .order_by('student__last_name')
    )
    if dept:
        placed_apps = placed_apps.filter(student__department=dept)

    filename = f"placement_report_{timezone.now().strftime('%Y%m%d')}.csv"
    response  = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Student Name', 'Matric Number', 'Department', 'Email',
        'Placement Title', 'Company', 'Location', 'Start Date', 'End Date',
        'Supervisor', 'Total Logs', 'Approved Logs', 'Log Approval %',
        'Mid-Term Score', 'Mid-Term Grade',
        'Final Score', 'Final Grade', 'Recommendation',
    ])

    for app in placed_apps:
        logs = LogbookEntry.objects.filter(application=app)
        total   = logs.count()
        approved = logs.filter(status='approved').count()
        pct     = round(approved / total * 100, 1) if total else 0

        mid   = Assessment.objects.filter(
            application=app, assessment_type='mid_term', status='submitted'
        ).first()
        final = Assessment.objects.filter(
            application=app, assessment_type='final', status='submitted'
        ).first()

        rec = ''
        if final and hasattr(final, 'summary'):
            rec = final.summary.get_recommendation_display()
        elif mid and hasattr(mid, 'summary'):
            rec = mid.summary.get_recommendation_display()

        writer.writerow([
            app.student.get_full_name(),
            app.student.matric_number,
            app.student.department,
            app.student.email,
            app.placement.title,
            app.placement.company_name,
            app.placement.location,
            app.placement.start_date.strftime('%Y-%m-%d'),
            app.placement.end_date.strftime('%Y-%m-%d'),
            app.supervisor.get_full_name() if app.supervisor else '',
            total,
            approved,
            f"{pct}%",
            f"{mid.total_score}/{mid.max_possible}" if mid else '',
            mid.grade_letter if mid else '',
            f"{final.total_score}/{final.max_possible}" if final else '',
            final.grade_letter if final else '',
            rec,
        ])

    return response