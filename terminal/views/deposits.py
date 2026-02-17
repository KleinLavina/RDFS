from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, DecimalField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.utils import is_staff_admin_or_admin
from terminal.models import SystemSettings
from vehicles.models import Deposit, Driver, Vehicle, Wallet


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def deposit_menu(request):
    settings = SystemSettings.get_solo()
    min_deposit = settings.min_deposit_amount
    wallet_search = request.GET.get("search_query", "").strip()
    wallet_sort = request.GET.get("wallet_sort", "newest").lower()
    if wallet_sort not in ("newest", "largest", "smallest", "driver_asc", "driver_desc"):
        wallet_sort = "newest"

    driver_qs = Driver.objects.filter(vehicles__isnull=False).distinct().prefetch_related("vehicles").order_by("last_name", "first_name")

    driver_options = []
    for driver in driver_qs:
        full_name = f"{driver.first_name} {driver.last_name}"
        license_text = driver.license_number or driver.driver_id or ""
        for vehicle in driver.vehicles.all():
            driver_options.append({
                "vehicle_id": vehicle.id,
                "license_plate": vehicle.license_plate,
                "driver_name": full_name,
                "license_number": license_text,
                "display": f"{full_name} · {vehicle.license_plate}",
            })

    wallets_qs = Wallet.objects.select_related("vehicle__assigned_driver").annotate(
        last_deposit_amount=Subquery(
            Deposit.objects.filter(wallet=OuterRef("pk"))
            .order_by("-created_at")
            .values("amount")[:1],
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        last_deposit_at=Subquery(
            Deposit.objects.filter(wallet=OuterRef("pk"))
            .order_by("-created_at")
            .values("created_at")[:1]
        ),
        deposit_count=Count("deposits"),
    )

    if wallet_search:
        wallets_qs = wallets_qs.filter(
            Q(vehicle__license_plate__icontains=wallet_search)
            | Q(vehicle__assigned_driver__first_name__icontains=wallet_search)
            | Q(vehicle__assigned_driver__last_name__icontains=wallet_search)
            | Q(vehicle__assigned_driver__license_number__icontains=wallet_search)
            | Q(vehicle__assigned_driver__driver_id__icontains=wallet_search)
        )

    if wallet_sort == "largest":
        ordering = ["-last_deposit_amount", "-last_deposit_at"]
    elif wallet_sort == "smallest":
        ordering = ["last_deposit_amount", "-last_deposit_at"]
    elif wallet_sort == "driver_asc":
        ordering = [
            "vehicle__assigned_driver__last_name",
            "vehicle__assigned_driver__first_name",
            "-last_deposit_at",
        ]
    elif wallet_sort == "driver_desc":
        ordering = [
            "-vehicle__assigned_driver__last_name",
            "-vehicle__assigned_driver__first_name",
            "-last_deposit_at",
        ]
    else:
        ordering = ["-last_deposit_at", "-updated_at"]

    wallets_count = wallets_qs.count()
    wallets_sorted = wallets_qs.order_by(*ordering)
    wallets = wallets_sorted[:80]

    if request.method == "POST":
        vehicle_id = request.POST.get("vehicle_id")
        amount_str = request.POST.get("amount", "").strip()

        if not vehicle_id or not amount_str:
            messages.error(request, "⚠️ Please fill in all required fields.")
            return redirect('terminal:deposit_menu')

        try:
            amount = Decimal(amount_str)
        except:
            messages.error(request, "❌ Invalid deposit amount.")
            return redirect('terminal:deposit_menu')

        if amount <= 0:
            messages.error(request, "⚠️ Deposit amount must be greater than zero.")
            return redirect('terminal:deposit_menu')

        vehicle = Vehicle.objects.filter(id=vehicle_id).first()
        if not vehicle:
            messages.error(request, "❌ Vehicle not found.")
            return redirect('terminal:deposit_menu')

        wallet, _ = Wallet.objects.get_or_create(vehicle=vehicle)
        Deposit.objects.create(wallet=wallet, amount=amount)

        messages.success(request, f"✅ Successfully deposited ₱{amount} to {vehicle.license_plate}.")
        return redirect('terminal:deposit_menu')

    toast_messages = [msg.message for msg in messages.get_messages(request)]

    context = {
        "min_deposit": min_deposit,
        "wallets": wallets,
        "wallets_total": wallets_count,
        "wallet_sort": wallet_sort,
        "wallet_search": wallet_search,
        "driver_options": driver_options,
        "toast_messages": toast_messages,
    }
    return render(request, "terminal/deposit_menu.html", context)


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def deposit_history(request):
    history_sort = request.GET.get("history_sort", "newest").lower()
    if history_sort not in ("newest", "largest", "smallest", "driver_asc", "driver_desc"):
        history_sort = "newest"
    history_query = request.GET.get("history_query", "").strip()

    deposits = Deposit.objects.select_related("wallet__vehicle__assigned_driver")

    if history_query:
        deposits = deposits.filter(
            Q(wallet__vehicle__license_plate__icontains=history_query)
            | Q(wallet__vehicle__assigned_driver__first_name__icontains=history_query)
            | Q(wallet__vehicle__assigned_driver__last_name__icontains=history_query)
            | Q(wallet__vehicle__assigned_driver__license_number__icontains=history_query)
            | Q(wallet__vehicle__assigned_driver__driver_id__icontains=history_query)
        )

    if history_sort == "largest":
        ordering = ["-amount", "-created_at"]
    elif history_sort == "smallest":
        ordering = ["amount", "-created_at"]
    elif history_sort == "driver_asc":
        ordering = [
            "wallet__vehicle__assigned_driver__last_name",
            "wallet__vehicle__assigned_driver__first_name",
            "-created_at",
        ]
    elif history_sort == "driver_desc":
        ordering = [
            "-wallet__vehicle__assigned_driver__last_name",
            "-wallet__vehicle__assigned_driver__first_name",
            "-created_at",
        ]
    else:
        ordering = ["-created_at"]

    deposits = deposits.order_by(*ordering)
    total_amount = deposits.aggregate(Sum("amount"))["amount__sum"] or 0
    total_count = deposits.count()

    context = {
        "history_deposits": deposits[:200],
        "history_sort": history_sort,
        "history_query": history_query,
        "total_amount": total_amount,
        "total_count": total_count,
    }
    return render(request, "terminal/deposit_history.html", context)


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def deposits(request):
    """Unified deposit management page with wallets and history."""
    import json
    
    settings = SystemSettings.get_solo()
    min_deposit = settings.min_deposit_amount
    
    # Get tab parameter
    active_tab = request.GET.get("tab", "wallets")
    
    # Driver options for modal
    driver_qs = Driver.objects.filter(vehicles__isnull=False).distinct().prefetch_related("vehicles").order_by("last_name", "first_name")
    driver_options = []
    for driver in driver_qs:
        full_name = f"{driver.first_name} {driver.last_name}"
        license_text = driver.license_number or driver.driver_id or ""
        for vehicle in driver.vehicles.all():
            driver_options.append({
                "vehicle_id": vehicle.id,
                "license_plate": vehicle.license_plate,
                "driver_name": full_name,
                "license_number": license_text,
                "display": f"{full_name} · {vehicle.license_plate}",
            })
    
    # WALLETS TAB DATA
    wallet_search = request.GET.get("search_query", "").strip()
    wallet_sort = request.GET.get("wallet_sort", "newest").lower()
    if wallet_sort not in ("newest", "largest", "smallest", "driver_asc", "driver_desc"):
        wallet_sort = "newest"
    
    wallets_qs = Wallet.objects.select_related("vehicle__assigned_driver").annotate(
        last_deposit_amount=Subquery(
            Deposit.objects.filter(wallet=OuterRef("pk"))
            .order_by("-created_at")
            .values("amount")[:1],
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        last_deposit_at=Subquery(
            Deposit.objects.filter(wallet=OuterRef("pk"))
            .order_by("-created_at")
            .values("created_at")[:1]
        ),
        deposit_count=Count("deposits"),
    )
    
    if wallet_search:
        wallets_qs = wallets_qs.filter(
            Q(vehicle__license_plate__icontains=wallet_search)
            | Q(vehicle__assigned_driver__first_name__icontains=wallet_search)
            | Q(vehicle__assigned_driver__last_name__icontains=wallet_search)
            | Q(vehicle__assigned_driver__license_number__icontains=wallet_search)
            | Q(vehicle__assigned_driver__driver_id__icontains=wallet_search)
        )
    
    if wallet_sort == "largest":
        ordering = ["-balance", "-last_deposit_at"]
    elif wallet_sort == "smallest":
        ordering = ["balance", "-last_deposit_at"]
    elif wallet_sort == "driver_asc":
        ordering = [
            "vehicle__assigned_driver__last_name",
            "vehicle__assigned_driver__first_name",
            "-last_deposit_at",
        ]
    elif wallet_sort == "driver_desc":
        ordering = [
            "-vehicle__assigned_driver__last_name",
            "-vehicle__assigned_driver__first_name",
            "-last_deposit_at",
        ]
    else:
        ordering = ["-last_deposit_at", "-updated_at"]
    
    wallets_count = wallets_qs.count()
    wallets_sorted = wallets_qs.order_by(*ordering)
    wallets = wallets_sorted[:80]
    
    # Wallet stats
    total_balance = wallets_qs.aggregate(Sum("balance"))["balance__sum"] or 0
    low_balance_count = wallets_qs.filter(balance__lt=min_deposit).count()
    total_deposits_count = Deposit.objects.count()
    
    # HISTORY TAB DATA
    from datetime import datetime
    import calendar
    
    # Get selected month/year from query params (default to current month)
    selected_month_str = request.GET.get("month", "")
    now = timezone.now()
    
    if selected_month_str:
        try:
            selected_date = datetime.strptime(selected_month_str, "%Y-%m")
            selected_year = selected_date.year
            selected_month = selected_date.month
        except ValueError:
            selected_year = now.year
            selected_month = now.month
    else:
        selected_year = now.year
        selected_month = now.month
    
    # Calculate month boundaries
    month_start = timezone.make_aware(datetime(selected_year, selected_month, 1))
    if selected_month == 12:
        month_end = timezone.make_aware(datetime(selected_year + 1, 1, 1)) - timedelta(seconds=1)
    else:
        month_end = timezone.make_aware(datetime(selected_year, selected_month + 1, 1)) - timedelta(seconds=1)
    
    history_sort = request.GET.get("history_sort", "newest").lower()
    if history_sort not in ("newest", "largest", "smallest", "driver_asc", "driver_desc"):
        history_sort = "newest"
    history_query = request.GET.get("history_query", "").strip()
    
    deposits_qs = Deposit.objects.select_related("wallet__vehicle__assigned_driver")
    
    # Filter by selected month
    deposits_qs = deposits_qs.filter(created_at__gte=month_start, created_at__lte=month_end)
    
    if history_query:
        deposits_qs = deposits_qs.filter(
            Q(wallet__vehicle__license_plate__icontains=history_query)
            | Q(wallet__vehicle__assigned_driver__first_name__icontains=history_query)
            | Q(wallet__vehicle__assigned_driver__last_name__icontains=history_query)
            | Q(wallet__vehicle__assigned_driver__license_number__icontains=history_query)
            | Q(wallet__vehicle__assigned_driver__driver_id__icontains=history_query)
        )
    
    if history_sort == "largest":
        ordering = ["-amount", "-created_at"]
    elif history_sort == "smallest":
        ordering = ["amount", "-created_at"]
    elif history_sort == "driver_asc":
        ordering = [
            "wallet__vehicle__assigned_driver__last_name",
            "wallet__vehicle__assigned_driver__first_name",
            "-created_at",
        ]
    elif history_sort == "driver_desc":
        ordering = [
            "-wallet__vehicle__assigned_driver__last_name",
            "-wallet__vehicle__assigned_driver__first_name",
            "-created_at",
        ]
    else:
        ordering = ["-created_at"]
    
    deposits_sorted = deposits_qs.order_by(*ordering)
    history_total = deposits_sorted.aggregate(Sum("amount"))["amount__sum"] or 0
    history_count = deposits_sorted.count()
    
    # Handle CSV Export
    export_action = request.GET.get("export", "")
    if export_action == "csv":
        import csv
        from django.http import HttpResponse
        from io import StringIO
        
        output = StringIO()
        output.write('\ufeff')  # UTF-8 BOM for Excel compatibility
        
        writer = csv.writer(output)
        writer.writerow([
            'Reference Number',
            'Date & Time',
            'Driver Name',
            'License Plate',
            'Amount',
            'Payment Method',
            'Status',
            'Processed By',
        ])
        
        for deposit in deposits_sorted:
            driver = deposit.wallet.vehicle.assigned_driver if deposit.wallet.vehicle else None
            driver_name = f"{driver.first_name} {driver.last_name}" if driver else "N/A"
            vehicle_plate = deposit.wallet.vehicle.license_plate if deposit.wallet.vehicle else "—"
            processed_by = deposit.created_by.username if deposit.created_by else "N/A"
            
            writer.writerow([
                deposit.reference_number,
                deposit.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                driver_name,
                vehicle_plate,
                f"₱{deposit.amount}",
                deposit.payment_method.upper(),
                deposit.status.capitalize(),
                processed_by,
            ])
        
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="deposits_{selected_year}_{selected_month:02d}.csv"'
        response.write(output.getvalue())
        return response
    
    history_deposits = deposits_sorted[:200]
    
    # Get available months with deposits for navigation
    available_months = (
        Deposit.objects
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .distinct()
        .order_by('-month')
    )
    
    # Calculate previous/next month
    current_month_date = datetime(selected_year, selected_month, 1)
    
    # Previous month
    if selected_month == 1:
        prev_month_date = datetime(selected_year - 1, 12, 1)
    else:
        prev_month_date = datetime(selected_year, selected_month - 1, 1)
    
    # Next month
    if selected_month == 12:
        next_month_date = datetime(selected_year + 1, 1, 1)
    else:
        next_month_date = datetime(selected_year, selected_month + 1, 1)
    
    # Make next_month_date timezone-aware for comparison
    next_month_date_aware = timezone.make_aware(next_month_date)
    
    # Check if prev/next months have data
    has_prev_month = Deposit.objects.filter(
        created_at__year=prev_month_date.year,
        created_at__month=prev_month_date.month
    ).exists()
    
    has_next_month = Deposit.objects.filter(
        created_at__year=next_month_date.year,
        created_at__month=next_month_date.month
    ).exists() and next_month_date_aware <= now
    
    # HANDLE POST (Add Deposit)
    if request.method == "POST":
        vehicle_id = request.POST.get("vehicle_id")
        amount_str = request.POST.get("amount", "").strip()
        
        if not vehicle_id or not amount_str:
            messages.error(request, "⚠️ Please fill in all required fields.")
            return redirect('terminal:deposits')
        
        try:
            amount = Decimal(amount_str)
        except:
            messages.error(request, "❌ Invalid deposit amount.")
            return redirect('terminal:deposits')
        
        if amount <= 0:
            messages.error(request, "⚠️ Deposit amount must be greater than zero.")
            return redirect('terminal:deposits')
        
        # ✅ VALIDATE MINIMUM DEPOSIT AMOUNT
        if amount < min_deposit:
            messages.error(request, f"❌ Deposit amount must be at least ₱{min_deposit}. You entered ₱{amount}.")
            return redirect('terminal:deposits')
        
        vehicle = Vehicle.objects.filter(id=vehicle_id).first()
        if not vehicle:
            messages.error(request, "❌ Vehicle not found.")
            return redirect('terminal:deposits')
        
        wallet, _ = Wallet.objects.get_or_create(vehicle=vehicle)
        deposit = Deposit.objects.create(wallet=wallet, amount=amount, created_by=request.user)
        
        messages.success(request, f"✅ Successfully deposited ₱{amount} to {vehicle.license_plate}.")
        
        # Redirect to receipt page
        return redirect('terminal:deposit_receipt', deposit_id=deposit.id)
    
    context = {
        "min_deposit": min_deposit,
        "wallets": wallets,
        "wallets_total": wallets_count,
        "wallet_sort": wallet_sort,
        "wallet_search": wallet_search,
        "total_balance": total_balance,
        "low_balance_count": low_balance_count,
        "total_deposits": total_deposits_count,
        "driver_options": json.dumps(driver_options),
        "history_deposits": history_deposits,
        "history_sort": history_sort,
        "history_query": history_query,
        "history_total": history_total,
        "history_count": history_count,
        "active_tab": active_tab,
        "selected_month": f"{selected_year}-{selected_month:02d}",
        "selected_month_name": current_month_date.strftime("%B %Y"),
        "prev_month": f"{prev_month_date.year}-{prev_month_date.month:02d}",
        "next_month": f"{next_month_date.year}-{next_month_date.month:02d}",
        "has_prev_month": has_prev_month,
        "has_next_month": has_next_month,
        "available_months": available_months,
    }
    return render(request, "terminal/deposits.html", context)



@login_required
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def deposit_receipt(request, deposit_id):
    """Generate printable wallet-size deposit receipt."""
    deposit = get_object_or_404(Deposit.objects.select_related('wallet__vehicle__assigned_driver'), id=deposit_id)
    
    vehicle = deposit.wallet.vehicle
    driver = vehicle.assigned_driver if vehicle else None
    
    context = {
        'deposit': deposit,
        'vehicle': vehicle,
        'driver': driver,
        'current_balance': deposit.wallet.balance,
    }
    
    return render(request, 'terminal/deposit_receipt.html', context)
