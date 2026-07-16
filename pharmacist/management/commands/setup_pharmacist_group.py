from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = 'Creates the Pharmacist group if it does not already exist.'

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name='Pharmacist')
        if created:
            self.stdout.write(self.style.SUCCESS('Pharmacist group created successfully.'))
        else:
            self.stdout.write(self.style.WARNING('Pharmacist group already exists.'))
