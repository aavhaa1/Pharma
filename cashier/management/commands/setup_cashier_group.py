from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = 'Creates the Cashier group if it does not already exist.'

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name='Cashier')
        if created:
            self.stdout.write(self.style.SUCCESS('Cashier group created successfully.'))
        else:
            self.stdout.write(self.style.WARNING('Cashier group already exists.'))
