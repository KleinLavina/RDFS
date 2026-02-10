from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.auth import logout, authenticate, login
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserEditForm
from vehicles.models import Driver, Vehicle, Deposit, QueueHistory
from terminal.models import EntryLog
from reports.models import Profit
from django.db.models import Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
from accounts.utils import is_admin, is_staff_admin, is_staff_admin_or_admin


# ===============================
# ✅ LOGIN VIEW (Secure & Role-Based)
# ===============================
@never_cache
def login_view(request):
    # Only redirect if user is already logged in
    if request.user.is_authenticated:
        if is_admin(request.user):
            return redirect('accounts:admin_dashboard')
        elif is_staff_admin(request.user):
            return redirect('accounts:staff_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            # Session expires on browser close
            request.session.set_expiry(0)
            request.session['role'] = getattr(user, 'role', '')
            request.session['secure_login'] = True
            request.session.modified = True

            if is_admin(user):
                return redirect('accounts:admin_dashboard')
            elif is_staff_admin(user):
                return redirect('accounts:staff_dashboard')
            else:
                messages.error(request, "Access denied: unauthorized role.")
                logout(request)
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'accounts/login.html')


# ===============================
# ✅ LOGOUT VIEW
# ===============================
@never_cache
def logout_view(request):
    logout(request)
    request.session.flush()
    messages.success(request, "You have been logged out successfully.")
    return redirect('accounts:login')


# ===============================
# ✅ MANAGE USERS
# ===============================
@login_required(login_url='login')
@user_passes_test(lambda u: is_admin(u) or is_staff_admin(u))
@never_cache
def manage_users(request):
    """Allow Admins and Staff Admins to view the user list."""
    if is_admin(request.user):
        users = CustomUser.objects.exclude(username=request.user.username).order_by('username')
    else:
        users = CustomUser.objects.filter(role='staff_admin').exclude(username=request.user.username)
    
    # Calculate stats
    admin_count = users.filter(role='admin').count()
    staff_admin_count = users.filter(role='staff_admin').count()
    
    context = {
        'users': users,
        'admin_count': admin_count,
        'staff_admin_count': staff_admin_count,
    }
    
    return render(request, 'accounts/manage_users.html', context)


# ===============================
# ✅ CREATE USER
# ===============================
@login_required(login_url='login')
@user_passes_test(lambda u: is_admin(u) or is_staff_admin(u))
@never_cache
def create_user(request):
    """Admins can create Admin and Staff Admin accounts; Staff Admins only Staff Admin."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, user=request.user)
        if form.is_valid():
            new_user = form.save()
            messages.success(request, f"✅ New {new_user.role.replace('_', ' ').title()} '{new_user.username}' created.")
            return redirect('accounts:manage_users')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomUserCreationForm(user=request.user)
    return render(request, 'accounts/create_user.html', {'form': form})


# ===============================
# ✅ EDIT USER
# ===============================
@login_required(login_url='login')
@user_passes_test(lambda u: is_admin(u) or is_staff_admin(u))
@never_cache
def edit_user(request, user_id):
    user_obj = get_object_or_404(CustomUser, id=user_id)

    # Prevent editing yourself
    if user_obj.id == request.user.id:
        messages.error(request, "You cannot edit your own account from this page.")
        return redirect('accounts:manage_users')
    
    # Only Staff Admins are blocked from editing Admin accounts
    # Admins CAN edit other Admin accounts
    if is_staff_admin(request.user) and user_obj.role == 'admin':
        messages.error(request, "Access denied: You cannot edit Admin accounts.")
        return redirect('accounts:manage_users')

    # Load the form
    form = CustomUserEditForm(request.POST or None, instance=user_obj)

    if request.method == 'POST':
        if form.is_valid():

            # Save username, email, role
            user = form.save(commit=False)
            user.save()

            # Handle password update if provided
            new_password = form.cleaned_data.get("new_password1")
            if new_password:
                user.set_password(new_password)
                user.save()
                messages.success(request, "User password updated successfully.")

            messages.success(request, f"User '{user.username}' updated successfully.")
            return redirect('accounts:manage_users')

        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, 'accounts/edit_user.html', {
        'form': form,
        'user_obj': user_obj
    })


# ===============================
# ✅ DELETE USER
# ===============================
@login_required(login_url='login')
@user_passes_test(is_admin)
@never_cache
def delete_user(request, user_id):
    user_obj = get_object_or_404(CustomUser, id=user_id)

    if request.method == 'POST':
        username = user_obj.username  # store before deleting
        user_obj.delete()
        messages.success(request, f"✅ User '{username}' deleted successfully.")
        return redirect('accounts:manage_users')

    context = {
        'user_obj': user_obj,  # required by delete_user.html
    }
    return render(request, 'accounts/delete_user.html', context)




# ===============================
# ✅ ADMIN DASHBOARD
# ===============================
@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(is_admin)
@never_cache
def admin_dashboard_view(request):
    from reports.models import Profit
    from django.db.models import Sum
    from datetime import datetime, timedelta
    from django.utils import timezone
    # Import QueueHistory from vehicles so the admin view and vehicles app are consistent
    try:
        from vehicles.models import QueueHistory
    except Exception:
        QueueHistory = None

    total_drivers = Driver.objects.count()
    total_vehicles = Vehicle.objects.count()

    # Active queue count: vehicles currently in terminal (is_active=True, status=success)
    total_queue = EntryLog.objects.filter(is_active=True, status=EntryLog.STATUS_SUCCESS).count()

    total_profit = Profit.objects.aggregate(Sum('amount'))['amount__sum'] or 0

    today = timezone.localtime().date()
    monthly_revenue = EntryLog.objects.filter(
        status=EntryLog.STATUS_SUCCESS,
        created_at__year=today.year,
        created_at__month=today.month,
    ).aggregate(Sum('fee_charged'))['fee_charged__sum'] or 0
    annual_revenue = EntryLog.objects.filter(
        status=EntryLog.STATUS_SUCCESS,
        created_at__year=today.year,
    ).aggregate(Sum('fee_charged'))['fee_charged__sum'] or 0

    context = {
        'total_drivers': total_drivers,
        'total_vehicles': total_vehicles,
        'total_queue': total_queue,
        'total_profit': total_profit,
        'monthly_revenue': monthly_revenue,
        'annual_revenue': annual_revenue,
        'now': timezone.now(),
    }
    return render(request, 'accounts/admin_dashboard.html', context)



# ===============================
# ✅ STAFF DASHBOARD
# ===============================
@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(is_staff_admin)
@never_cache
def staff_dashboard_view(request):
    total_drivers = Driver.objects.count()
    total_vehicles = Vehicle.objects.count()
    # Active queue count: vehicles currently in terminal (is_active=True, status=success)
    total_queue = EntryLog.objects.filter(is_active=True, status=EntryLog.STATUS_SUCCESS).count()

    context = {
        'total_drivers': total_drivers,
        'total_vehicles': total_vehicles,
        'total_queue': total_queue,
    }
    return render(request, 'accounts/staff_dashboard.html', context)



@login_required(login_url='login')
@user_passes_test(is_admin)
def admin_dashboard_data(request):
    """AJAX endpoint for admin dashboard live data."""
    total_drivers = Driver.objects.count()
    total_vehicles = Vehicle.objects.count()
    total_queue = EntryLog.objects.filter(is_active=True, status="success").count()

    # Totals
    total_deposits = Deposit.objects.aggregate(total=Sum("amount"))["total"] or 0
    total_revenue = EntryLog.objects.filter(status="success").aggregate(total=Sum("fee_charged"))["total"] or 0
    total_profit = Profit.objects.aggregate(total=Sum("amount"))["total"] or 0

    # Last 7 days profit trend
    now = timezone.localtime()
    start_date = now - timedelta(days=6)
    chart_labels, chart_data = [], []

    for i in range(7):
        day = (start_date + timedelta(days=i)).date()
        total = (
            Profit.objects.filter(date_recorded__date=day)
            .aggregate(Sum("amount"))["amount__sum"]
            or 0
        )
        chart_labels.append(day.strftime("%b %d"))
        chart_data.append(float(total))

    # Recent queue list for optional display
    recent_queues = list(
        EntryLog.objects.filter(is_active=True, status="success")
        .select_related("vehicle__assigned_driver")
        .order_by("-created_at")[:10]
        .values("vehicle__license_plate", "vehicle__assigned_driver__first_name", "vehicle__assigned_driver__last_name")
    )

    return JsonResponse({
        "total_drivers": total_drivers,
        "total_vehicles": total_vehicles,
        "total_deposits": float(total_deposits),
        "total_revenue": float(total_revenue),
        "total_profit": float(total_profit),
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "recent_queues": recent_queues,
    })