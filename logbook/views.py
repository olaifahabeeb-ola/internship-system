from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from datetime import timedelta, date

from accounts.decorators import (
    student_required, supervisor_required,
    coordinator_required, supervisor_or_coordinator_required,
)
from accounts.models import CustomUser
from notifications.utils import send_notification
from placements.models import Application
from .models import LogbookEntry, WeeklyReport
from .forms import (
    LogbookEntryForm, ReviewLogEntryForm,
    BulkApproveForm, WeeklyReportForm, LogFilterForm
)


# ── Helpers ───────────────────────────────────────────────────────

def _get_student_application(user):
    """Return the student's accepted Application or None."""
    return (
        Application.objects
        .filter(student=user, status='accepted')
        .select_related('placement', 'supervisor')
        .first()
    )

def _apply_log_filters(qs, form):
    """Apply LogFilterForm values to a LogbookEntry queryset."""
    if not form.is_valid():
        return qs
    status    = form.cleaned_data.get('status')
    date_from = form.cleaned_data.get('date_from')
    date_to   = form.cleaned_data.get('date_to')
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


# ══════════════════════════════════════════════════════════════════
#  STUDENT VIEWS
# ══════════════════════════════════════════════════════════════════

@student_required
def submit_log(request):
    """Student submits a new daily logbook entry."""
    application = _get_student_application(request.user)
    if not application:
        messages.error(
            request,
            "You must be accepted for a placement before you can submit log entries."
        )
        return redirect('placements:list')

    form = LogbookEntryForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.application = application

        errors = []
        log_date = form.cleaned_data.get('date')

        if log_date:
            if log_date > timezone.now().date():
                form.add_error('date', 'Log date cannot be in the future.')
            elif log_date < application.placement.start_date:
                form.add_error('date',
                    f'Date is before your placement start date '
                    f'({application.placement.start_date}).')
            elif log_date > application.placement.end_date:
                form.add_error('date',
                    f'Date is after your placement end date '
                    f'({application.placement.end_date}).')
            elif LogbookEntry.objects.filter(
                    application=application, date=log_date).exists():
                form.add_error('date',
                    'You have already submitted a log entry for this date.')
            else:
                entry.save()
                messages.success(
                    request,
                    f'Log entry for {entry.date} submitted successfully!'
                )
                return redirect('logbook:my_logbook')

    context = {
        'form':        form,
        'application': application,
    }
    return render(request, 'logbook/submit_log.html', context)


@student_required
def my_logbook(request):
    """Student views all their log entries with filter + pagination."""
    application = _get_student_application(request.user)
    if not application:
        messages.info(request, "You are not yet placed. No logbook entries to show.")
        return redirect('accounts:student_dashboard')

    entries = LogbookEntry.objects.filter(application=application)

    filter_form = LogFilterForm(request.GET or None)
    entries = _apply_log_filters(entries, filter_form)
    entries = entries.order_by('-date')

    total    = LogbookEntry.objects.filter(application=application).count()
    pending  = LogbookEntry.objects.filter(application=application, status='pending').count()
    approved = LogbookEntry.objects.filter(application=application, status='approved').count()
    rejected = LogbookEntry.objects.filter(application=application, status='rejected').count()

    streak     = 0
    check_date = timezone.now().date()
    all_dates  = set(
        LogbookEntry.objects
        .filter(application=application, status__in=['pending', 'approved'])
        .values_list('date', flat=True)
    )
    while check_date in all_dates:
        streak    += 1
        check_date = check_date - timedelta(days=1)

    week_start    = timezone.now().date() - timedelta(days=timezone.now().weekday())
    approved_week = LogbookEntry.objects.filter(
        application=application,
        status='approved',
        date__gte=week_start,
    ).count()

    paginator   = Paginator(entries, 12)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {
        'page_obj':      page_obj,
        'filter_form':   filter_form,
        'application':   application,
        'stats': {
            'total':          total,
            'pending':        pending,
            'approved':       approved,
            'rejected':       rejected,
            'streak':         streak,
            'approved_week':  approved_week,
        },
    }
    return render(request, 'logbook/my_logbook.html', context)


@student_required
def log_detail(request, pk):
    """Student views a single log entry."""
    application = _get_student_application(request.user)
    entry = get_object_or_404(LogbookEntry, pk=pk, application=application)
    return render(request, 'logbook/log_detail.html', {'entry': entry})


@student_required
def edit_log(request, pk):
    """Student edits a pending log entry."""
    application = _get_student_application(request.user)
    entry = get_object_or_404(LogbookEntry, pk=pk, application=application)

    if not entry.is_editable:
        messages.error(request, "Only pending entries can be edited.")
        return redirect('logbook:log_detail', pk=pk)

    form = LogbookEntryForm(
        request.POST or None,
        request.FILES or None,
        instance=entry,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Log entry updated.")
        return redirect('logbook:log_detail', pk=pk)

    context = {'form': form, 'entry': entry, 'application': application}
    return render(request, 'logbook/submit_log.html', context)


@student_required
def delete_log(request, pk):
    """Student deletes a pending log entry (POST only)."""
    application = _get_student_application(request.user)
    entry = get_object_or_404(LogbookEntry, pk=pk, application=application)

    if not entry.is_editable:
        messages.error(request, "Only pending entries can be deleted.")
        return redirect('logbook:log_detail', pk=pk)

    if request.method == 'POST':
        entry.delete()
        messages.success(request, f"Log entry for {entry.date} deleted.")
        return redirect('logbook:my_logbook')

    return render(request, 'logbook/confirm_delete.html', {'entry': entry})


@student_required
def submit_weekly_report(request):
    """Student submits a weekly summary report."""
    application = _get_student_application(request.user)
    if not application:
        messages.error(request, "You must be placed before submitting reports.")
        return redirect('accounts:student_dashboard')

    form = WeeklyReportForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        report = form.save(commit=False)
        report.application = application

        if WeeklyReport.objects.filter(
                application=application,
                week_start=report.week_start).exists():
            form.add_error('week_start',
                           'You have already submitted a report for this week.')
        else:
            report.save()
            messages.success(request, 'Weekly report submitted successfully!')
            return redirect('logbook:my_weekly_reports')

    context = {'form': form, 'application': application}
    return render(request, 'logbook/submit_weekly_report.html', context)


@student_required
def my_weekly_reports(request):
    """Student views all their weekly reports."""
    application = _get_student_application(request.user)
    if not application:
        return redirect('accounts:student_dashboard')

    reports = WeeklyReport.objects.filter(application=application)
    context = {'reports': reports, 'application': application}
    return render(request, 'logbook/my_weekly_reports.html', context)


# ══════════════════════════════════════════════════════════════════
#  SUPERVISOR VIEWS
# ══════════════════════════════════════════════════════════════════

@supervisor_required
def supervisor_student_list(request):
    """Supervisor sees all students assigned to them."""
    inactive_threshold = getattr(settings, 'LOGBOOK_INACTIVE_DAYS', 5)
    cutoff = timezone.now().date() - timedelta(days=inactive_threshold)

    supervised = (
        Application.objects
        .filter(supervisor=request.user, status='accepted')
        .select_related('student', 'placement')
        .annotate(
            total_logs    = Count('log_entries'),
            pending_logs  = Count('log_entries',
                                  filter=Q(log_entries__status='pending')),
            approved_logs = Count('log_entries',
                                  filter=Q(log_entries__status='approved')),
        )
    )

    inactive_ids = set()
    for app in supervised:
        last_entry = (
            LogbookEntry.objects
            .filter(application=app)
            .order_by('-date')
            .values_list('date', flat=True)
            .first()
        )
        if last_entry is None or last_entry < cutoff:
            inactive_ids.add(app.pk)

    pending_total = LogbookEntry.objects.filter(
        application__supervisor=request.user,
        status='pending',
    ).count()

    context = {
        'supervised':     supervised,
        'inactive_ids':   inactive_ids,
        'pending_total':  pending_total,
        'inactive_days':  inactive_threshold,
    }
    return render(request, 'logbook/supervisor_student_list.html', context)


@supervisor_required
def supervisor_student_logbook(request, app_pk):
    """Supervisor views a single student's full logbook."""
    application = get_object_or_404(
        Application,
        pk=app_pk,
        supervisor=request.user,
        status='accepted',
    )

    entries = LogbookEntry.objects.filter(application=application)
    filter_form = LogFilterForm(request.GET or None)
    entries = _apply_log_filters(entries, filter_form)
    entries = entries.order_by('-date')

    paginator   = Paginator(entries, 12)
    page_obj    = paginator.get_page(request.GET.get('page'))

    context = {
        'application': application,
        'page_obj':    page_obj,
        'filter_form': filter_form,
    }
    return render(request, 'logbook/supervisor_student_logbook.html', context)


@supervisor_required
def review_list(request):
    """Supervisor sees all pending log entries across their students."""
    entries = (
        LogbookEntry.objects
        .filter(application__supervisor=request.user, status='pending')
        .select_related('application__student', 'application__placement')
        .order_by('date')
    )
    context = {'entries': entries}
    return render(request, 'logbook/review_list.html', context)


@supervisor_required
def supervisor_review_log(request, pk):
    """
    Supervisor reviews (approve/reject) a single log entry.
    GET  → show detail + review form.
    POST → process decision.
    """
    entry = get_object_or_404(
        LogbookEntry.objects.select_related(
            'application__student', 'application__placement'
        ),
        pk=pk,
        application__supervisor=request.user,
    )

    form = ReviewLogEntryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        entry.mark_reviewed(
            supervisor=request.user,
            status=form.cleaned_data['status'],
            comment=form.cleaned_data.get('supervisor_comment', ''),
        )
        send_notification(
            user=entry.application.student,
            message=f'Your logbook entry for {entry.date} was {entry.status}.',
            notification_type='logbook',
            link=reverse('logbook:my_logbook'),
        )
        verb = 'approved' if entry.status == 'approved' else 'rejected'
        messages.success(
            request,
            f"Log entry for {entry.date} has been {verb}."
        )
        return redirect('logbook:review_list')

    context = {'entry': entry, 'form': form}
    return render(request, 'logbook/supervisor_review_log.html', context)


@supervisor_required
def bulk_approve(request):
    """
    POST: supervisor bulk-approves a list of pending entry IDs.
    IDs arrive as a comma-separated hidden field from the review list.
    """
    if request.method != 'POST':
        return redirect('logbook:review_list')

    form = BulkApproveForm(request.POST)
    if form.is_valid():
        ids = form.cleaned_data['entry_ids']
        updated = (
            LogbookEntry.objects
            .filter(
                pk__in=ids,
                application__supervisor=request.user,
                status='pending',
            )
        )
        entries_to_notify = list(
            updated.select_related('application__student')
        )
        count = updated.count()
        updated.update(
            status='approved',
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        for entry in entries_to_notify:
            send_notification(
                user=entry.application.student,
                message=f'Your logbook entry for {entry.date} was approved.',
                notification_type='logbook',
                link=reverse('logbook:my_logbook'),
            )
        messages.success(request, f"{count} log entr{'y' if count == 1 else 'ies'} approved.")
    else:
        messages.error(request, "No entries selected.")

    return redirect('logbook:review_list')


@supervisor_required
def supervisor_weekly_reports(request, app_pk):
    """Supervisor views a student's weekly reports."""
    application = get_object_or_404(
        Application,
        pk=app_pk,
        supervisor=request.user,
        status='accepted',
    )
    reports = WeeklyReport.objects.filter(application=application)
    context = {'reports': reports, 'application': application}
    return render(request, 'logbook/supervisor_weekly_reports.html', context)


# ══════════════════════════════════════════════════════════════════
#  COORDINATOR VIEWS
# ══════════════════════════════════════════════════════════════════

@coordinator_required
def coordinator_monitor(request):
    """Coordinator monitoring dashboard — all students across all placements."""
    behind_days = getattr(settings, 'LOGBOOK_BEHIND_DAYS', 7)
    cutoff = timezone.now().date() - timedelta(days=behind_days)

    dept = (request.user.department or request.user.faculty or '').strip()
    all_apps = (
        Application.objects
        .filter(placement__posted_by=request.user, status='accepted')
        .select_related('student', 'placement', 'supervisor')
        .annotate(
            total_logs   = Count('log_entries'),
            pending_logs = Count('log_entries',
                                 filter=Q(log_entries__status='pending')),
        )
    )

    if dept:
        all_apps = all_apps.filter(student__department=dept)

    behind_ids = set()
    for app in all_apps:
        last = (
            LogbookEntry.objects
            .filter(application=app)
            .order_by('-date')
            .values_list('date', flat=True)
            .first()
        )
        if last is None or last < cutoff:
            behind_ids.add(app.pk)

    total_entries_this_week = LogbookEntry.objects.filter(
        application__placement__posted_by=request.user,
        date__gte=timezone.now().date() - timedelta(days=7),
    ).count()

    total_pending = LogbookEntry.objects.filter(
        application__placement__posted_by=request.user,
        status='pending',
    ).count()

    chart_labels = []
    chart_data   = []
    for i in range(13, -1, -1):
        day = timezone.now().date() - timedelta(days=i)
        count = LogbookEntry.objects.filter(
            application__placement__posted_by=request.user,
            date=day,
        ).count()
        chart_labels.append(day.strftime('%d %b'))
        chart_data.append(count)

    import json
    context = {
        'all_apps':                 all_apps,
        'behind_ids':               behind_ids,
        'behind_days':              behind_days,
        'total_entries_this_week':  total_entries_this_week,
        'total_pending':            total_pending,
        'total_placed':             all_apps.count(),
        'total_behind':             len(behind_ids),
        'chart_labels':             json.dumps(chart_labels),
        'chart_data':               json.dumps(chart_data),
    }
    return render(request, 'logbook/coordinator_monitor.html', context)


@coordinator_required
def coordinator_student_logbook(request, app_pk):
    """Coordinator views any student's logbook (read-only)."""
    application = get_object_or_404(
        Application,
        pk=app_pk,
        placement__posted_by=request.user,
        status='accepted',
    )

    entries = LogbookEntry.objects.filter(application=application)
    filter_form = LogFilterForm(request.GET or None)
    entries = _apply_log_filters(entries, filter_form)
    entries = entries.order_by('-date')

    paginator = Paginator(entries, 12)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'application': application,
        'page_obj':    page_obj,
        'filter_form': filter_form,
        'readonly':    True,
    }
    return render(request, 'logbook/coordinator_student_logbook.html', context)


# ── Shared detail view (supervisor + coordinator) ──────────────────

@login_required
def review_detail(request, pk):
    """
    Supervisor OR coordinator reviews a single log entry.
    A coordinator can review any log entry tied to a placement they
    posted — this is the fallback path for when a placement's
    supervisor is unavailable, hasn't logged in, or is simply slow,
    so a pending entry is never permanently stuck with no one able
    to act on it. Reuses ReviewLogEntryForm as-is; the decision and
    comment fields mean the same thing regardless of who's reviewing.
    """
    if request.user.is_coordinator:
        entry = get_object_or_404(
            LogbookEntry,
            pk=pk,
            application__placement__posted_by=request.user,
        )
        form = ReviewLogEntryForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            entry.mark_reviewed(
                supervisor=request.user,
                status=form.cleaned_data['status'],
                comment=form.cleaned_data.get('supervisor_comment', ''),
            )
            send_notification(
                user=entry.application.student,
                message=f'Your logbook entry for {entry.date} was {entry.status}.',
                notification_type='logbook',
                link=reverse('logbook:my_logbook'),
            )
            verb = 'approved' if entry.status == 'approved' else 'rejected'
            messages.success(request, f"Log entry for {entry.date} has been {verb}.")
            return redirect('logbook:coordinator_overview')
        context = {'entry': entry, 'form': form}
        return render(request, 'logbook/coordinator_review_log.html', context)

    # Supervisor path — unchanged
    return redirect('logbook:supervisor_review_log', pk=pk)


@coordinator_required
def student_logbook(request, app_pk):
    """Alias used by the coordinator dashboard 'behind students' links."""
    return coordinator_student_logbook(request, app_pk)
