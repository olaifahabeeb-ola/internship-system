from django.db import migrations


def backfill_created_by(apps, schema_editor):
    Placement = apps.get_model('placements', 'Placement')
    for placement in Placement.objects.all():
        if placement.created_by_id is None and placement.posted_by_id is not None:
            placement.created_by_id = placement.posted_by_id
            placement.save(update_fields=['created_by'])


def reverse_noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('placements', '0002_placement_created_by'),
    ]

    operations = [
        migrations.RunPython(backfill_created_by, reverse_noop),
    ]
