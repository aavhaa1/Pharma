def is_admin(user):
    return user.groups.filter(name="Admin").exists()


def is_pharmacist(user):
    return user.groups.filter(name="Pharmacist").exists()


def is_cashier(user):
    return user.groups.filter(name="Cashier").exists()

