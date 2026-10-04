import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Create/update the non-privileged demo user; optional password from KHANE_DEMO_PASSWORD.'

    @transaction.atomic
    def handle(self, *args, **options):
        user, created = get_user_model().objects.get_or_create(username=settings.DEMO_USERNAME)
        if user.is_staff or user.is_superuser:
            raise CommandError('Refusing to reuse a privileged user as the public demo account.')
        user.first_name = 'کاربر آزمایشی'
        user.is_active = True
        password = os.environ.get('KHANE_DEMO_PASSWORD')
        if password:
            user.set_password(password)
        elif created:
            user.set_unusable_password()
        user.save()
        self.stdout.write(self.style.SUCCESS('Demo user ready (password never printed).'))
