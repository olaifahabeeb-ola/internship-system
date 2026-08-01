from django.db import migrations


def backfill_from_coordinator(apps, schema_editor):
    Announcement = apps.get_model('announcements', 'Announcement')
    User = apps.get_model('accounts', 'CustomUser')

    faculty_to_department = {
        'School of Computing': 'Computer Science',
        'School of Business': 'Business Administration',
    }

    for announcement in Announcement.objects.all():
        if announcement.target_department:
            continue

        if announcement.target_audience not in {'students', 'specific_department'}:
            continue

        posted_by = announcement.posted_by
        if not posted_by:
            continue

        department = getattr(posted_by, 'department', '') or ''
        if not department:
            department = faculty_to_department.get(getattr(posted_by, 'faculty', ''), '')

        if department:
            announcement.target_department = department
            announcement.save(update_fields=['target_department'])

    for user in User.objects.filter(role='coordinator'):
        if getattr(user, 'department', ''):
            continue

        inferred = faculty_to_department.get(getattr(user, 'faculty', ''), '')
        if inferred:
            user.department = inferred
            user.save(update_fields=['department'])


def reverse_noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0003_backfill_announcement_target_department'),
        ('accounts', '0002_alter_customuser_faculty'),
    ]

    operations = [
        migrations.RunPython(backfill_from_coordinator, reverse_noop),
    ]
