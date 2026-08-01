import csv
import io
import json
from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.urls import reverse

from .forms import RegistrationForm, LoginForm, ProfileUpdateForm
from .models import CustomUser, DEPARTMENT_CHOICES


# ── Auth ──────────────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'Welcome, {user.first_name}! Account created.')
        return redirect('accounts:dashboard')
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, f'Welcome back, {user.first_name or user.username}!')
        return redirect(request.GET.get('next', 'accounts:dashboard'))
    elif request.method == 'POST':
        messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


# ── Central role router ───────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    """
    Single entry point after login. Admin status (is_superuser / is_staff)
    is checked FIRST and always wins — it is never derived from `role`.
    """
    user = request.user

    if user.is_admin:
        return redirect('accounts:admin_dashboard')

    role = user.role
    if role == 'student':
        return redirect('accounts:student_dashboard')
    elif role == 'supervisor':
        return redirect('accounts:supervisor_dashboard')
    elif role == 'coordinator':
        return redirect('accounts:coordinator_dashboard')

    messages.error(request, 'Your account has no role assigned. Contact the administrator.')
    logout(request)
    return redirect('accounts:login')


# ── Helper: get coordinator's department ─────────────────────────────────────

def _coord_dept(coordinator):
    """Returns the coordinator's department string."""
    return (coordinator.department or coordinator.faculty or '').strip()


# ── Admin Dashboard ───────────────────────────────────────────────────────────

@login_required
def admin_dashboard(request):
    if not request.user.is_admin:
        messages.error(request, 'You do not have permission to view that page.')
        return redirect('accounts:dashboard')

    from placements.models import Placement, Application
    from logbook.models import LogbookEntry
    from announcements.models import Announcement

    total_students     = CustomUser.objects.filter(role='student').count()
    total_supervisors  = CustomUser.objects.filter(role='supervisor').count()
    total_coordinators = CustomUser.objects.filter(role='coordinator').count()
    total_users        = CustomUser.objects.count()

    total_placements       = Placement.objects.count()
    total_applications     = Application.objects.count()
    pending_applications   = Application.objects.filter(status='pending').count()
    accepted_applications  = Application.objects.filter(status='accepted').count()

    total_logs   = LogbookEntry.objects.count()
    pending_logs = LogbookEntry.objects.filter(status='pending').count()

    total_announcements = Announcement.objects.count()

    dept_breakdown = (
        CustomUser.objects.filter(role='student')
        .exclude(department='')
        .values('department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    recent_users = CustomUser.objects.order_by('-date_joined')[:8]

    context = {
        'total_users':           total_users,
        'total_students':        total_students,
        'total_supervisors':     total_supervisors,
        'total_coordinators':    total_coordinators,
        'total_placements':      total_placements,
        'total_applications':    total_applications,
        'pending_applications':  pending_applications,
        'accepted_applications': accepted_applications,
        'total_logs':            total_logs,
        'pending_logs':          pending_logs,
        'total_announcements':   total_announcements,
        'dept_breakdown':        dept_breakdown,
        'recent_users':          recent_users,
        'notif_count':           pending_applications + pending_logs,
    }
    return render(request, 'accounts/dashboard_admin.html', context)


# ── Student Dashboard ─────────────────────────────────────────────────────────

@login_required
def student_dashboard(request):
    if not request.user.is_student:
        messages.error(request, 'That page is only available to students.')
        return redirect('accounts:dashboard')

    from placements.models import Application
    from logbook.models import LogbookEntry
    from announcements.models import Announcement
    from assessment.models import Assessment

    applications = Application.objects.filter(student=request.user)
    app_counts = {
        'pending':  applications.filter(status='pending').count(),
        'accepted': applications.filter(status='accepted').count(),
        'rejected': applications.filter(status='rejected').count(),
    }
    accepted_application = (
        applications.filter(status='accepted')
        .select_related('placement', 'supervisor').first()
    )

    log_stats   = {'total': 0, 'pending': 0, 'approved_week': 0, 'streak': 0}
    recent_logs = []
    placement_progress = {'label': 'Not Found', 'state': 'missing', 'percent': 0, 'color': 'danger'}
    logbook_progress = {'submitted': 0, 'total': 12, 'percent': 0, 'state': 'missing', 'color': 'danger'}
    assessment_progress = {
        'mid_term': {'done': False, 'state': 'missing'},
        'final': {'done': False, 'state': 'missing'},
        'overall_state': 'missing',
    }
    next_action = {
        'tone': 'warning',
        'title': "You haven't applied yet.",
        'message': 'Browse available placements and submit your first application.',
        'button_text': 'Browse placements',
        'url': reverse('placements:list'),
    }
    latest_assessment = None

    if accepted_application:
        placement_progress = {'label': 'Found', 'state': 'complete', 'percent': 100, 'color': 'success'}
        logs_qs    = LogbookEntry.objects.filter(application=accepted_application)
        week_start = timezone.now().date() - timedelta(days=timezone.now().weekday())
        log_stats['total']         = logs_qs.count()
        log_stats['pending']       = logs_qs.filter(status='pending').count()
        log_stats['approved_week'] = logs_qs.filter(
            status='approved', date__gte=week_start).count()
        all_dates  = set(logs_qs.filter(
            status__in=['pending', 'approved']).values_list('date', flat=True))
        check_date = timezone.now().date()
        streak = 0
        while check_date in all_dates:
            streak    += 1
            check_date = check_date - timedelta(days=1)
        log_stats['streak'] = streak
        recent_logs = logs_qs.order_by('-date')[:5]

        today = timezone.now().date()
        current_week_start = today - timedelta(days=today.weekday())
        submitted_weeks = 0
        for week_offset in range(12):
            week_start = current_week_start - timedelta(weeks=week_offset)
            week_end = week_start + timedelta(days=6)
            if logs_qs.filter(date__range=[week_start, week_end]).exists():
                submitted_weeks += 1
        percent = round((submitted_weeks / 12) * 100)
        if submitted_weeks == 12:
            state, color = 'complete', 'success'
        elif submitted_weeks > 0:
            state, color = 'progress', 'warning'
        else:
            state, color = 'missing', 'danger'
        logbook_progress = {'submitted': submitted_weeks, 'total': 12, 'percent': percent, 'state': state, 'color': color}

        mid_term_done = Assessment.objects.filter(
            application=accepted_application, assessment_type='mid_term', status='submitted'
        ).exists()
        final_done = Assessment.objects.filter(
            application=accepted_application, assessment_type='final', status='submitted'
        ).exists()
        overall_state = 'complete' if mid_term_done and final_done else 'progress' if mid_term_done or final_done else 'missing'
        overall_color = 'success' if overall_state == 'complete' else 'warning' if overall_state == 'progress' else 'danger'
        assessment_progress = {
            'mid_term': {'done': mid_term_done, 'state': 'complete' if mid_term_done else 'missing'},
            'final': {'done': final_done, 'state': 'complete' if final_done else 'missing'},
            'overall_state': overall_state,
            'overall_color': overall_color,
        }

        if logbook_progress['submitted'] == 0:
            next_action = {
                'tone': 'info',
                'title': 'Start your logbook.',
                'message': "Submit this week's entry to keep your internship record current.",
                'button_text': 'Submit entry',
                'url': reverse('logbook:submit_entry'),
            }
        else:
            next_action = {
                'tone': 'success',
                'title': 'You are on track.',
                'message': 'Keep submitting weekly logbook entries and assessments.',
                'button_text': 'View logbook',
                'url': reverse('logbook:my_logbook'),
            }

        latest_assessment = (
            Assessment.objects
            .filter(application=accepted_application, status='submitted')
            .order_by('-submission_date').first()
        )

    announcements = Announcement.for_user(request.user)[:5]
    notif_count   = log_stats['pending']

    context = {
        'accepted_application': accepted_application,
        'app_counts':           app_counts,
        'log_stats':            log_stats,
        'recent_logs':          recent_logs,
        'latest_assessment':    latest_assessment,
        'announcements':        announcements,
        'notif_count':          notif_count,
        'placement_progress':   placement_progress,
        'logbook_progress':     logbook_progress,
        'assessment_progress':  assessment_progress,
        'next_action':          next_action,
    }
    return render(request, 'accounts/dashboard_student.html', context)


# ── Supervisor Dashboard ──────────────────────────────────────────────────────

@login_required
def supervisor_dashboard(request):
    if not request.user.is_supervisor:
        messages.error(request, 'That page is only available to industry supervisors.')
        return redirect('accounts:dashboard')

    from placements.models import Application, Placement
    from logbook.models import LogbookEntry
    from assessment.models import Assessment
    from announcements.models import Announcement
    from django.conf import settings

    inactive_threshold = getattr(settings, 'LOGBOOK_INACTIVE_DAYS', 5)
    cutoff      = timezone.now().date() - timedelta(days=inactive_threshold)
    month_start = timezone.now().date().replace(day=1)

    supervised = (
        Application.objects
        .filter(supervisor=request.user, status='accepted')
        .select_related('student', 'placement')
    )
    pending_logs = (
        LogbookEntry.objects
        .filter(application__supervisor=request.user, status='pending')
        .select_related('application__student')
        .order_by('-date')[:8]
    )
    approved_month = LogbookEntry.objects.filter(
        application__supervisor=request.user,
        status='approved',
        reviewed_at__date__gte=month_start,
    ).count()

    inactive_students = []
    for app in supervised:
        last = (
            LogbookEntry.objects.filter(application=app)
            .order_by('-date').values_list('date', flat=True).first()
        )
        if last is None or last < cutoff:
            inactive_students.append(app)

    pending_mid = pending_final = 0
    for app in supervised:
        if not Assessment.objects.filter(
                application=app, assessment_type='mid_term',
                status='submitted').exists():
            pending_mid += 1
        if not Assessment.objects.filter(
                application=app, assessment_type='final',
                status='submitted').exists():
            pending_final += 1

    pending_count = LogbookEntry.objects.filter(
        application__supervisor=request.user, status='pending').count()
    announcements = Announcement.for_user(request.user)[:5]
    notif_count   = pending_count

    assigned_students = []
    for app in supervised:
        latest_log = LogbookEntry.objects.filter(application=app).order_by('-date').first()
        if latest_log is None:
            status, last_log_date = 'pending', None
        elif (timezone.now().date() - latest_log.date).days > inactive_threshold:
            status, last_log_date = 'overdue', latest_log.date
        else:
            status, last_log_date = 'submitted', latest_log.date
        assigned_students.append({
            'application': app,
            'last_log_date': last_log_date,
            'status': status,
        })

    # ── Placement postings submitted by this supervisor (Feature 1) ──
    my_placements = Placement.objects.filter(
        submitted_by=request.user
    ).order_by('-created_at')
    placement_counts = {
        'pending':  my_placements.filter(approval_status='pending').count(),
        'approved': my_placements.filter(approval_status='approved').count(),
        'rejected': my_placements.filter(approval_status='rejected').count(),
    }
    recent_placements = my_placements[:5]

    next_action = {
        'tone': 'info',
        'title': 'Review pending logs.',
        'message': f'You have {pending_count} logs waiting for review.',
        'button_text': 'Review logs',
        'url': reverse('logbook:review_list'),
    } if pending_count else {
        'tone': 'success',
        'title': 'All reviews are current.',
        'message': 'No student logs are awaiting your review right now.',
        'button_text': 'View students',
        'url': reverse('logbook:supervisor_student_list'),
    }

    context = {
        'supervised':         supervised,
        'pending_logs':       pending_logs,
        'student_count':      supervised.count(),
        'pending_count':      pending_count,
        'approved_month':     approved_month,
        'inactive_count':     len(inactive_students),
        'inactive_students':  inactive_students,
        'pending_mid':        pending_mid,
        'pending_final':      pending_final,
        'announcements':      announcements,
        'notif_count':        notif_count,
        'assigned_students':  assigned_students,
        'placement_counts':   placement_counts,
        'recent_placements':  recent_placements,
        'next_action':        next_action,
    }
    return render(request, 'accounts/dashboard_supervisor.html', context)


# ── Coordinator Dashboard ─────────────────────────────────────────────────────

@login_required
def coordinator_dashboard(request):
    if not request.user.is_coordinator:
        messages.error(request, 'That page is only available to school coordinators.')
        return redirect('accounts:dashboard')

    from placements.models import Placement, Application
    from logbook.models import LogbookEntry
    from assessment.models import Assessment
    from announcements.models import Announcement
    from django.conf import settings

    behind_days = getattr(settings, 'LOGBOOK_BEHIND_DAYS', 7)
    cutoff      = timezone.now().date() - timedelta(days=behind_days)
    coord       = request.user
    dept        = _coord_dept(coord)

    dept_students = CustomUser.objects.filter(role='student')
    if dept:
        dept_students = dept_students.filter(department=dept)

    my_placements = Placement.objects.filter(created_by=coord).order_by('-created_at')

    my_applications = Application.objects.filter(
        placement__posted_by=coord,
        student__department=dept,
    ) if dept else Application.objects.filter(placement__posted_by=coord).none()

    placed_apps = my_applications.filter(status='accepted').select_related(
        'student', 'placement', 'supervisor'
    )

    total_students    = dept_students.count()
    total_placed      = placed_apps.count()
    total_placements  = my_placements.count()
    pending_apps      = my_applications.filter(status='pending').count()

    pending_log_reviews = LogbookEntry.objects.filter(
        application__placement__posted_by=coord,
        status='pending',
    ).count()

    pending_assessments = 0
    for app in placed_apps:
        if not Assessment.objects.filter(
                application=app, assessment_type='mid_term',
                status='submitted').exists():
            pending_assessments += 1
        if not Assessment.objects.filter(
                application=app, assessment_type='final',
                status='submitted').exists():
            pending_assessments += 1

    total_announcements = Announcement.objects.filter(posted_by=coord).count()

    # ── Placement submissions awaiting this coordinator's approval ──
    # (Feature 1) Scoped to this coordinator's own department — a
    # coordinator only reviews vacancies targeting the students they
    # actually manage, matching review_placement's permission check.
    pending_placements = (
        Placement.objects
        .filter(target_department=dept, approval_status='pending')
        .select_related('submitted_by')
    ) if dept else Placement.objects.none()
    pending_placement_count = pending_placements.count()

    log_chart_labels = []
    log_chart_data   = []
    for i in range(13, -1, -1):
        day   = timezone.now().date() - timedelta(days=i)
        count = LogbookEntry.objects.filter(
            application__placement__posted_by=coord,
            date=day,
        ).count()
        log_chart_labels.append(day.strftime('%d %b'))
        log_chart_data.append(count)

    per_company = (
        placed_apps.values('placement__company_name')
        .annotate(count=Count('id')).order_by('-count')
    )
    company_chart_data = {
        'labels': [r['placement__company_name'] for r in per_company],
        'data':   [r['count'] for r in per_company],
    }

    at_risk = []
    for app in placed_apps:
        last = (
            LogbookEntry.objects.filter(application=app)
            .order_by('-date').values_list('date', flat=True).first()
        )
        days_since = (timezone.now().date() - last).days if last else 999
        if days_since >= behind_days:
            at_risk.append({'app': app, 'days_since': days_since})
    at_risk.sort(key=lambda x: x['days_since'], reverse=True)

    pending_actions = []
    for app in my_applications.filter(status='pending').select_related(
            'student', 'placement')[:4]:
        pending_actions.append({
            'type':        'Application',
            'colour':      'warning',
            'description': f"{app.student.get_full_name()} applied for {app.placement.title}",
            'url':         f'/placements/coordinator/{app.placement.pk}/applications/',
        })
    for log in LogbookEntry.objects.filter(
            application__placement__posted_by=coord,
            status='pending').select_related('application__student')[:4]:
        pending_actions.append({
            'type':        'Log Review',
            'colour':      'info',
            'description': f"{log.student.get_full_name()} — log for {log.date}",
            'url':         f'/logbook/review/{log.pk}/',
        })
    for p in pending_placements.order_by('-created_at')[:4]:
        submitter_name = p.submitted_by.get_full_name() if p.submitted_by else 'A supervisor'
        pending_actions.append({
            'type':        'Placement Submission',
            'colour':      'info',
            'description': f'{submitter_name} submitted "{p.title}" at {p.company_name}',
            'url':         f'/placements/coordinator/pending/{p.pk}/review/',
        })

    recent_activity = []
    for app in my_applications.select_related(
            'student', 'placement').order_by('-applied_at')[:4]:
        recent_activity.append({
            'icon':        'bi-file-earmark-plus',
            'colour':      '#0d6efd',
            'description': f"{app.student.get_full_name()} applied for {app.placement.title}",
            'timestamp':   app.applied_at,
            'url':         f'/placements/coordinator/{app.placement.pk}/applications/',
        })
    for log in LogbookEntry.objects.filter(
            application__placement__posted_by=coord
            ).select_related('application__student').order_by('-created_at')[:4]:
        recent_activity.append({
            'icon':        'bi-journal-plus',
            'colour':      '#198754',
            'description': f"{log.student.get_full_name()} submitted a log for {log.date}",
            'timestamp':   log.created_at,
            'url':         f'/logbook/monitor/student/{log.application.pk}/',
        })
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:10]

    recent_announcements = Announcement.objects.filter(
        posted_by=coord).order_by('-created_at')[:5]

    notif_count = pending_apps + pending_log_reviews + pending_placement_count

    next_action = {
        'tone': 'warning',
        'title': 'Students need attention.',
        'message': f'{len(at_risk)} students are behind on logbooks this week.',
        'button_text': 'View monitor',
        'url': reverse('logbook:coordinator_overview'),
    } if at_risk else {
        'tone': 'success',
        'title': 'Everything is current.',
        'message': 'No students are behind on logbook submissions this week.',
        'button_text': 'View monitor',
        'url': reverse('logbook:coordinator_overview'),
    }

    context = {
        'coordinator_dept': dept or 'All Departments',
        'total_students':       total_students,
        'total_placed':         total_placed,
        'total_placements':     total_placements,
        'pending_apps':         pending_apps,
        'pending_log_reviews':  pending_log_reviews,
        'pending_assessments':  pending_assessments,
        'total_announcements':  total_announcements,
        'my_placements':        my_placements,
        'placed_students_count': total_placed,
        'pending_review_count': pending_log_reviews,
        'behind_students_count': len(at_risk),
        'pending_placement_count': pending_placement_count,
        'log_chart_labels':    json.dumps(log_chart_labels),
        'log_chart_data':      json.dumps(log_chart_data),
        'company_chart_data':  json.dumps(company_chart_data),
        'at_risk':             at_risk,
        'pending_actions':     pending_actions,
        'recent_activity':     recent_activity,
        'recent_announcements':recent_announcements,
        'notif_count':         notif_count,
        'next_action':         next_action,
    }
    return render(request, 'accounts/dashboard_coordinator.html', context)


# ── Students by Department (coordinator's own dept, or ALL for admin) ─────────

@login_required
def coordinator_students_by_dept(request):
    from placements.models import Application

    user = request.user
    is_admin_view = user.is_admin

    students = CustomUser.objects.filter(role='student')
    dept = ''

    if is_admin_view:
        pass
    else:
        dept = _coord_dept(user)
        if dept:
            students = students.filter(department=dept)
        else:
            students = students.none()

    prog_filter   = request.GET.get('programme', '')
    level_filter  = request.GET.get('level', '')
    placed_filter = request.GET.get('placed', '')

    if prog_filter:
        students = students.filter(programme=prog_filter)
    if level_filter:
        students = students.filter(level=level_filter)

    students = students.order_by('last_name')

    if is_admin_view:
        placed_ids = set(
            Application.objects.filter(status='accepted').values_list('student_id', flat=True)
        )
    elif dept:
        placed_ids = set(
            Application.objects
            .filter(placement__posted_by=user, status='accepted', student__department=dept)
            .values_list('student_id', flat=True)
        )
    else:
        placed_ids = set()

    if placed_filter == 'placed':
        students = students.filter(pk__in=placed_ids)
    elif placed_filter == 'unplaced':
        students = students.exclude(pk__in=placed_ids)

    from itertools import groupby
    students_list = list(students)
    grouped = {}
    for s in students_list:
        level = s.get_level_display() if s.level else 'Not Specified'
        if level not in grouped:
            grouped[level] = {'students': [], 'placed': 0, 'unplaced': 0}
        grouped[level]['students'].append(s)
        if s.pk in placed_ids:
            grouped[level]['placed'] += 1
        else:
            grouped[level]['unplaced'] += 1

    context = {
        'grouped':       grouped,
        'placed_ids':    placed_ids,
        'prog_filter':   prog_filter,
        'level_filter':  level_filter,
        'placed_filter': placed_filter,
        'total':         len(students_list),
        'dept':          'All Departments' if is_admin_view else (dept or 'All Departments'),
    }
    return render(request, 'accounts/coordinator_students.html', context)


# ── Bulk Student Upload ───────────────────────────────────────────────────────

@login_required
def bulk_upload_students(request):
    results = None
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        decoded  = csv_file.read().decode('utf-8')
        reader   = csv.DictReader(io.StringIO(decoded))
        created  = []
        skipped  = []
        errors   = []

        coord_dept = '' if request.user.is_admin else _coord_dept(request.user)

        for i, row in enumerate(reader, start=2):
            username = row.get('username', '').strip()
            matric   = row.get('matric_number', '').strip()
            email    = row.get('email', '').strip()

            if not username or not matric:
                errors.append(f"Row {i}: username and matric_number are required.")
                continue

            if CustomUser.objects.filter(username=username).exists():
                skipped.append(f"{username} (duplicate username)")
                continue
            if CustomUser.objects.filter(matric_number=matric, role='student').exists():
                skipped.append(f"{username} (duplicate matric: {matric})")
                continue

            password = f"Student@{matric[-4:]}" if len(matric) >= 4 else "Student@1234"
            try:
                user = CustomUser.objects.create_user(
                    username         = username,
                    email            = email,
                    password         = password,
                    first_name       = row.get('first_name', '').strip(),
                    last_name        = row.get('last_name', '').strip(),
                    role             = 'student',
                    matric_number    = matric,
                    department       = row.get('department', coord_dept).strip() or coord_dept,
                    programme        = row.get('programme', '').strip(),
                    level            = row.get('level', '').strip(),
                    academic_session = row.get('academic_session', '2024/2025').strip(),
                )
                created.append({
                    'name':     user.get_full_name(),
                    'username': username,
                    'password': password,
                })
            except Exception as e:
                errors.append(f"Row {i} ({username}): {e}")

        results = {'created': created, 'skipped': skipped, 'errors': errors}

    return render(request, 'accounts/bulk_upload.html', {'results': results})


# ── Profile ───────────────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    form = ProfileUpdateForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {'form': form})