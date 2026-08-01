from .models import Notification


def send_notification(user, message, notification_type='application', link=''):
    """
    Creates a Notification row for `user`. The navbar's polling JS
    picks this up on its next check (every ~8 seconds) — no
    WebSocket or channel layer needed, since delivery just means
    "show up in the next poll," not an instant push.
    """
    return Notification.objects.create(
        user=user,
        message=message,
        notification_type=notification_type,
        link=link,
    )