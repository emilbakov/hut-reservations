from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0015_managerdigestpreference'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HutQuickReply',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=80)),
                ('subject', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('enabled', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hut', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quick_replies', to='bookings.hut')),
            ],
            options={'ordering': ['title', 'pk']},
        ),
        migrations.AddConstraint(
            model_name='hutquickreply',
            constraint=models.UniqueConstraint(fields=('hut', 'title'), name='unique_hut_quick_reply'),
        ),
        migrations.CreateModel(
            name='GuestConversationMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender', models.CharField(choices=[('guest', 'Guest'), ('manager', 'Manager')], max_length=10)),
                ('subject', models.CharField(blank=True, max_length=200)),
                ('body', models.TextField()),
                ('recipient', models.EmailField(blank=True, max_length=254)),
                ('delivery', models.CharField(choices=[('received', 'Received in SummitDesk'), ('in_app', 'In-app only'), ('sending', 'Email sending'), ('sent', 'Email submitted'), ('failed', 'Email failed (in-app delivered)')], max_length=12)),
                ('error', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('hut', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='conversation_messages', to='bookings.hut')),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_messages', to='bookings.reservation')),
                ('sent_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sent_guest_conversation_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['created_at', 'pk']},
        ),
        migrations.AddIndex(
            model_name='guestconversationmessage',
            index=models.Index(fields=['reservation', 'created_at'], name='guest_conversation_idx'),
        ),
    ]
