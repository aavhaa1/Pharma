from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = "Create default user groups"

    def handle(self, *args, **kwargs):
        groups = ["Admin", "Pharmacist", "Cashier"]

        for group in groups:
            Group.objects.get_or_create(name=group)

        self.stdout.write(self.style.SUCCESS("Groups created successfully!"))