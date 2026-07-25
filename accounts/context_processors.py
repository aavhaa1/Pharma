from django.conf import settings


def base_template(request):
    """
    Returns the appropriate base template depending on the user's role.
    Cashiers get 'cashier/base_cashier.html'.
    Admins and Pharmacists get 'base.html'.
    Also provides global pharmacy configuration settings.
    """
    context = {
        'PHARMACY_ADDRESS': getattr(settings, 'PHARMACY_ADDRESS', 'Chyasal, Lalitpur'),
        'pharmacy_address': getattr(settings, 'PHARMACY_ADDRESS', 'Chyasal, Lalitpur'),
    }

    if request.user.is_authenticated:
        if request.user.groups.filter(name='Cashier').exists() and not request.user.is_superuser:
            context['base_template'] = 'cashier/base_cashier.html'
            return context

    # Default for Admin, Pharmacist, and unauthenticated users
    context['base_template'] = 'base.html'
    return context

