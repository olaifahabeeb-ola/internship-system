from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from accounts.decorators import coordinator_required
from accounts.models import CustomUser
from .models import Announcement
from .forms import AnnouncementForm


# ── Coordinator ───────────────────────────────────────────────────

@coordinator_required
def coordinator_create(request):
    """
    Coordinator posts announcement.
    Target audience is scoped to their own department students automatically.
    """
    coord = request.user
    dept  = (coord.department or coord.faculty or '').strip()

    form = AnnouncementForm(request.POST or None, coordinator=coord)

    if request.method == 'POST' and form.is_valid():
        ann = form.save(commit=False)
        ann.posted_by = coord
        # Defensive re-assignment — this is the REAL enforcement for a
        # brand-new announcement, not just the form's disabled field.
        # See AnnouncementForm.__init__ for the full explanation.
        if dept:
            ann.target_department = dept
        ann.save()
        messages.success(request, f'Announcement "{ann.title}" posted.')
        return redirect('announcements:coordinator_list')

    context = {
        'form': form,
        'dept': dept,
    }
    return render(request, 'announcements/coordinator_create.html', context)


@coordinator_required
def coordinator_list(request):
    announcements = Announcement.objects.filter(
        posted_by=request.user
    ).order_by('-created_at')
    return render(request, 'announcements/coordinator_list.html',
                  {'announcements': announcements})


@coordinator_required
def coordinator_edit(request, pk):
    coord = request.user
    dept  = (coord.department or coord.faculty or '').strip()
    ann   = get_object_or_404(Announcement, pk=pk, posted_by=coord)
    form  = AnnouncementForm(
        request.POST or None,
        instance=ann,
        coordinator=coord,
    )
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        if dept:
            updated.target_department = dept
        updated.save()
        messages.success(request, 'Announcement updated.')
        return redirect('announcements:coordinator_list')
    return render(request, 'announcements/coordinator_create.html',
                  {'form': form, 'editing': True, 'announcement': ann, 'dept': dept})


@coordinator_required
def coordinator_delete(request, pk):
    ann = get_object_or_404(Announcement, pk=pk, posted_by=request.user)
    if request.method == 'POST':
        ann.delete()
        messages.success(request, 'Announcement deleted.')
        return redirect('announcements:coordinator_list')
    return render(request, 'announcements/confirm_delete.html',
                  {'announcement': ann})


@coordinator_required
def coordinator_toggle(request, pk):
    ann = get_object_or_404(Announcement, pk=pk, posted_by=request.user)
    if request.method == 'POST':
        ann.is_active = not ann.is_active
        ann.save(update_fields=['is_active'])
        status = 'activated' if ann.is_active else 'archived'
        messages.info(request, f'Announcement "{ann.title}" {status}.')
    return redirect('announcements:coordinator_list')


# ── Shared (all authenticated roles) ─────────────────────────────

@login_required
def announcement_list(request):
    announcements = Announcement.for_user(request.user)
    return render(request, 'announcements/list.html',
                  {'announcements': announcements})


@login_required
def announcement_detail(request, pk):
    ann = get_object_or_404(Announcement, pk=pk, is_active=True)
    visible = Announcement.for_user(request.user).filter(pk=pk).exists()
    if not visible and not request.user.is_coordinator:
        messages.error(request,
                       "You don't have permission to view that announcement.")
        return redirect('announcements:list')
    return render(request, 'announcements/detail.html',
                  {'announcement': ann})