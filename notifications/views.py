from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .models import Notification


@login_required
def poll(request):
    """
    Hit every few seconds by base.html's JS. Returns the unread count
    plus the most recent notifications, so the navbar dropdown always
    has something to show even once everything's been read.
    """
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    data = {
        'unread_count': unread_count,
        'notifications': [
            {
                'id':                n.pk,
                'message':           n.message,
                'notification_type': n.notification_type,
                'link':              n.link,
                'is_read':           n.is_read,
                'created_at':        n.created_at.strftime('%d %b, %H:%M'),
            }
            for n in qs
        ],
    }
    return JsonResponse(data)


@login_required
def notification_list(request):
    """Full notification history page — filterable, paginated."""
    qs = Notification.objects.filter(user=request.user)

    type_filter = request.GET.get('type', '')
    if type_filter:
        qs = qs.filter(notification_type=type_filter)

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj':     page_obj,
        'type_filter':  type_filter,
        'type_choices': Notification.TYPE_CHOICES,
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'notifications/list.html', context)


@login_required
def mark_read(request, pk):
    """Mark one notification read, then follow its link (or back to the list)."""
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.mark_read()
    if notif.link:
        return redirect(notif.link)
    return redirect('notifications:list')


@login_required
def mark_all_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications:list')