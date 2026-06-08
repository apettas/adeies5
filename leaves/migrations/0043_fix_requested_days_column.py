from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Fix: migration 0039 used SeparateDatabaseAndState (no actual ALTER TABLE).
    This runs the real AddField so the column exists in the database.
    """

    dependencies = [
        ('leaves', '0042_add_yearly_sick_leave_total'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='requested_days',
            field=models.PositiveIntegerField(
                default=1,
                verbose_name='Αιτούμενες Ημέρες Άδειας',
            ),
        ),
    ]