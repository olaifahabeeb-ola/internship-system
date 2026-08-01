from django.db import migrations


def backfill_target_department(apps, schema_editor):
    Announcement = apps.get_model('announcements', 'Announcement')
    for announcement in Announcement.objects.all():
        if announcement.target_department:
            continue

        if announcement.target_audience in {'students', 'specific_department'}:
            posted_by = announcement.posted_by
            if posted_by:
                department = getattr(posted_by, 'department', '') or ''
                if department:
                    announcement.target_department = department
                    announcement.save(update_fields=['target_department'])


def reverse_noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0002_announcement_target_department_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_target_department, reverse_noop),
    ]
