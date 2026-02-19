from django.contrib.auth.decorators import user_passes_test

# ✅ Allow both admin and staff_admin
def is_staff_admin_or_admin(user):
    return user.is_authenticated and user.role in ['staff_admin', 'admin']

# ✅ Strictly admin only
def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

# ✅ Strictly staff_admin only
def is_staff_admin(user):
    return user.is_authenticated and user.role == 'staff_admin'

# ✅ Strictly treasurer only
def is_treasurer(user):
    return user.is_authenticated and user.role == 'treasurer'
