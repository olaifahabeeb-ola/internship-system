def sidebar_badges(request):
    """
    Makes role-appropriate notification counts available on EVERY page,
    not just the dashboard. Without this, the navbar bell icon and the
    sidebar's "Applications" / "Review Logbooks" / "Pending Approvals"
    badges only appeared while viewing the dashboard itself — every other
    page (e.g. coordinator_pending_placements, review_application,
    my_logbook) had no such variable in context, so the badge silently
    vanished the moment you clicked off the dashboard.

    Uses DIFFERENT variable names (global_notif_count,
    global_pending_placement_count) rather than reusing notif_count /
    pending_placement_count on purpose: Django context processors take
    precedence over same-named keys in a view's own context dict, so
    reusing those names here would silently overwrite each dashboard
    view's own carefully-scoped computation. The numbers below are
    written to match each dashboard's own logic exactly, so there's no
    visible discrepancy between the navbar badge and the in-page stat
    card on the dashboard itself.
    """
    if not request.user.is_authenticated:
        return {'global_notif_count': 0, 'global_pending_placement_count': 0}

    user = request.user

    try:
        if user.is_admin:
            from placements.models import Application
            from logbook.models import LogbookEntry
            count = (
                Application.objects.filter(status='pending').count()
                + LogbookEntry.objects.filter(status='pending').count()
            )
            return {'global_notif_count': count, 'global_pending_placement_count': 0}

        if user.is_coordinator:
            from placements.models import Placement, Application
            from logbook.models import LogbookEntry

            dept = (user.department or user.faculty or '').strip()

            if dept:
                pending_apps = Application.objects.filter(
                    placement__posted_by=user,
                    student__department=dept,
                    status='pending',
                ).count()
                pending_placements = Placement.objects.filter(
                    target_department=dept, approval_status='pending'
                ).count()
            else:
                pending_apps = 0
                pending_placements = 0

            pending_log_reviews = LogbookEntry.objects.filter(
                application__placement__posted_by=user, status='pending'
            ).count()

            return {
                'global_notif_count': pending_apps + pending_log_reviews + pending_placements,
                'global_pending_placement_count': pending_placements,
            }

        if user.is_supervisor:
            from logbook.models import LogbookEntry
            count = LogbookEntry.objects.filter(
                application__supervisor=user, status='pending'
            ).count()
            return {'global_notif_count': count, 'global_pending_placement_count': 0}

        if user.is_student:
            from logbook.models import LogbookEntry
            from placements.models import Application
            accepted = Application.objects.filter(student=user, status='accepted').first()
            count = 0
            if accepted:
                count = LogbookEntry.objects.filter(
                    application=accepted, status='pending'
                ).count()
            return {'global_notif_count': count, 'global_pending_placement_count': 0}

    except Exception:
        # A context processor runs on EVERY page load. A badge-count
        # failure here must never take down the entire site — fail
        # quietly to zero instead of 500ing every page.
        pass

    return {'global_notif_count': 0, 'global_pending_placement_count': 0}