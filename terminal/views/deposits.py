from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, DecimalField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_exempt
from django.db import models

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
    """Unified deposit management page with wallets, approved deposits, and pending approvals."""
    import json
    
    settings = SystemSettings.get_solo()
    min_deposit = settings.min_deposit_amount
    
    # Get tab parameter
    active_tab = request.GET.get("tab", "wallets")
    
    # HANDLE POST (Approve/Reject Deposits)
    if request.method == "POST":
        deposit_id = request.POST.get('deposit_id')
        action = request.POST.get('action')  # 'approve' or 'reject'
        
        try:
            deposit = Deposit.objects.select_related(
                'wallet__vehicle',
                'created_by'
            ).get(id=deposit_id, status=Deposit.STATUS_PENDING)
            
            if action == 'approve':
                deposit.status = Deposit.STATUS_APPROVED
                deposit.approved_by = request.user
                deposit.approved_at = timezone.now()
                deposit.save()
                
                # Wallet is credited automatically in Deposit.save()
                messages.success(
                    request,
                    f'Deposit {deposit.or_code} approved! '
                    f'₱{deposit.amount} credited to {deposit.wallet.vehicle.vehicle_name}.'
                )
            elif action == 'reject':
                deposit.status = Deposit.STATUS_REJECTED
                deposit.approved_by = request.user
                deposit.approved_at = timezone.now()
                deposit.save()
                
                messages.warning(
                    request,
                    f'Deposit {deposit.or_code} rejected. No wallet update.'
                )
            
        except Deposit.DoesNotExist:
            messages.error(request, 'Deposit not found or already processed.')
        except Exception as e:
            messages.error(request, f'Error processing deposit: {str(e)}')
        
        # Redirect back to pending tab
        from django.urls import reverse
        return redirect(reverse('terminal:deposits') + '?tab=pending')
    
    # WALLETS TAB DATA
    wallet_search = request.GET.get("search_query", "").strip()
    wallet_sort = request.GET.get("wallet_sort", "newest").lower()
    if wallet_sort not in ("newest", "largest", "smallest", "driver_asc", "driver_desc"):
        wallet_sort = "newest"
    
    # Filter wallets to show only approved deposits
    wallets_qs = Wallet.objects.select_related("vehicle__assigned_driver").annotate(
        last_deposit_amount=Subquery(
            Deposit.objects.filter(
                wallet=OuterRef("pk"),
                status__in=[Deposit.STATUS_APPROVED, Deposit.STATUS_SUCCESSFUL]
            )
            .order_by("-created_at")
            .values("amount")[:1],
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        last_deposit_at=Subquery(
            Deposit.objects.filter(
                wallet=OuterRef("pk"),
                status__in=[Deposit.STATUS_APPROVED, Deposit.STATUS_SUCCESSFUL]
            )
            .order_by("-created_at")
            .values("created_at")[:1]
        ),
        deposit_count=Count(
            "deposits",
            filter=models.Q(deposits__status__in=[Deposit.STATUS_APPROVED, Deposit.STATUS_SUCCESSFUL])
        ),
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
    
    # Filter to show ONLY approved deposits
    deposits_qs = Deposit.objects.filter(
        status__in=[Deposit.STATUS_APPROVED, Deposit.STATUS_SUCCESSFUL]
    ).select_related("wallet__vehicle__assigned_driver", "approved_by")
    
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
        .filter(status__in=[Deposit.STATUS_APPROVED, Deposit.STATUS_SUCCESSFUL])
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
        created_at__month=next_month_date.month,
        status__in=[Deposit.STATUS_APPROVED, Deposit.STATUS_SUCCESSFUL]
    ).exists() and next_month_date_aware <= now
    
    # PENDING DEPOSITS TAB DATA
    pending_deposits = Deposit.objects.filter(
        status=Deposit.STATUS_PENDING
    ).select_related(
        'wallet__vehicle__assigned_driver',
        'created_by'
    ).order_by('-created_at')
    
    pending_count = pending_deposits.count()
    
    # Context for template
    context = {
        "min_deposit": min_deposit,
        "wallets": wallets,
        "wallets_total": wallets_count,
        "wallet_sort": wallet_sort,
        "wallet_search": wallet_search,
        "total_balance": total_balance,
        "low_balance_count": low_balance_count,
        "total_deposits": total_deposits_count,
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
        "pending_deposits": pending_deposits,
        "pending_count": pending_count,
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


# ===============================
# ✅ TREASURER VIEWS
# ===============================

@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(lambda u: u.is_authenticated and u.role == 'treasurer')
@never_cache
@xframe_options_exempt
def treasurer_request_deposit(request):
    """Treasurer form to request a deposit after receiving payment from driver."""
    
    if request.method == 'POST':
        driver_id = request.POST.get('driver')
        amount = request.POST.get('amount')
        or_code = request.POST.get('or_code', '').strip()
        notes = request.POST.get('notes', '').strip()
        
        # Validation
        if not driver_id or not amount or not or_code:
            messages.error(request, 'Driver, amount, and OR Code are required.')
            return redirect('terminal:treasurer_request_deposit')
        
        try:
            driver = Driver.objects.get(id=driver_id)
            # Get the first vehicle assigned to this driver
            vehicle = driver.vehicles.first()
            
            if not vehicle:
                messages.error(request, 'This driver has no assigned vehicle.')
                return redirect('terminal:treasurer_request_deposit')
            
            wallet = vehicle.wallet
            amount_decimal = Decimal(amount)
            
            # Get minimum deposit from system settings
            system_settings = SystemSettings.get_solo()
            if amount_decimal < system_settings.min_deposit_amount:
                messages.error(
                    request,
                    f'Deposit amount cannot be lower than the minimum required deposit of ₱{system_settings.min_deposit_amount}.'
                )
                return redirect('terminal:treasurer_request_deposit')
            
            if amount_decimal <= 0:
                messages.error(request, 'Amount must be greater than zero.')
                return redirect('terminal:treasurer_request_deposit')
            
            # Check if OR code is unique (required field)
            if Deposit.objects.filter(or_code=or_code).exists():
                messages.error(request, f'OR Code "{or_code}" already exists. Please use a unique code.')
                return redirect('terminal:treasurer_request_deposit')
            
            # Create deposit request with PENDING status
            deposit = Deposit.objects.create(
                wallet=wallet,
                amount=amount_decimal,
                or_code=or_code,
                status=Deposit.STATUS_PENDING,
                created_by=request.user,
                notes=notes,
                payment_method='cash'
            )
            
            # Add success message
            messages.success(
                request,
                f'✅ Deposit request created successfully! OR Code: {or_code} for ₱{amount_decimal}. Awaiting approval.'
            )
            
            # Render printable receipt
            context = {
                'deposit': deposit,
                'driver': driver,
                'vehicle': vehicle,
                'treasurer': request.user,
                'timestamp': deposit.created_at,
                'in_modal': request.GET.get('modal') == '1',
            }
            
            # Redirect to receipt page instead of rendering directly
            if request.GET.get('modal') == '1':
                # For modal, render receipt with modal flag
                return render(request, 'terminal/treasurer_deposit_receipt_print.html', context)
            else:
                # For standalone, redirect to receipt page
                return redirect('terminal:treasurer_deposit_receipt', deposit_id=deposit.id)
            
        except Driver.DoesNotExist:
            messages.error(request, 'Driver not found.')
        except Exception as e:
            messages.error(request, f'Error creating deposit request: {str(e)}')
        
        return redirect('terminal:treasurer_request_deposit')
    
    # GET request - show form
    # Get system settings for frontend validation
    system_settings = SystemSettings.get_solo()
    
    context = {
        'min_deposit_amount': system_settings.min_deposit_amount,
    }
    
    # Check if this is a modal request
    if request.GET.get('modal') == '1':
        return render(request, 'terminal/treasurer_request_deposit_modal.html', context)
    else:
        return render(request, 'terminal/treasurer_request_deposit.html', context)


@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(lambda u: u.is_authenticated and u.role == 'treasurer')
@never_cache
def treasurer_receipts(request):
    """View all deposit requests created by this treasurer."""
    deposits = Deposit.objects.filter(
        created_by=request.user
    ).select_related(
        'wallet__vehicle__assigned_driver',
        'approved_by'
    ).order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        deposits = deposits.filter(status=status_filter)
    
    context = {
        'deposits': deposits,
        'status_filter': status_filter,
    }
    return render(request, 'terminal/treasurer_receipts.html', context)


@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(lambda u: u.is_authenticated and u.role in ['treasurer', 'admin', 'staff_admin'])
@never_cache
def treasurer_deposit_details(request, deposit_id):
    """View detailed information about a specific deposit request."""
    deposit = get_object_or_404(
        Deposit.objects.select_related(
            'wallet__vehicle__assigned_driver',
            'created_by',
            'approved_by'
        ),
        id=deposit_id
    )
    
    vehicle = deposit.wallet.vehicle
    driver = vehicle.assigned_driver if vehicle else None
    
    context = {
        'deposit': deposit,
        'vehicle': vehicle,
        'driver': driver,
    }
    return render(request, 'terminal/treasurer_deposit_details.html', context)


@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(lambda u: u.is_authenticated and u.role in ['treasurer', 'admin', 'staff_admin'])
@never_cache
def treasurer_deposit_receipt(request, deposit_id):
    """View printable receipt for a specific deposit request."""
    deposit = get_object_or_404(
        Deposit.objects.select_related(
            'wallet__vehicle__assigned_driver',
            'created_by'
        ),
        id=deposit_id
    )
    
    vehicle = deposit.wallet.vehicle
    driver = vehicle.assigned_driver if vehicle else None
    
    # Check if this is a fresh submission (show success toast)
    show_success = request.session.pop('show_deposit_success', False)
    or_code = request.session.pop('deposit_or_code', '')
    amount = request.session.pop('deposit_amount', '')
    
    context = {
        'deposit': deposit,
        'vehicle': vehicle,
        'driver': driver,
        'treasurer': deposit.created_by,
        'timestamp': deposit.created_at,
        'in_modal': False,
        'show_success': show_success,
        'success_or_code': or_code,
        'success_amount': amount,
    }
    return render(request, 'terminal/treasurer_deposit_receipt_print.html', context)


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def admin_approve_deposits(request):
    """Admin/Staff Admin page to approve or reject pending deposit requests."""
    if request.method == 'POST':
        deposit_id = request.POST.get('deposit_id')
        action = request.POST.get('action')  # 'approve' or 'reject'
        
        try:
            deposit = Deposit.objects.select_related(
                'wallet__vehicle',
                'created_by'
            ).get(id=deposit_id, status=Deposit.STATUS_PENDING)
            
            if action == 'approve':
                deposit.status = Deposit.STATUS_APPROVED
                deposit.approved_by = request.user
                deposit.approved_at = timezone.now()
                deposit.save()
                
                # Wallet is credited automatically in Deposit.save()
                messages.success(
                    request,
                    f'Deposit {deposit.or_code} approved! '
                    f'₱{deposit.amount} credited to {deposit.wallet.vehicle.vehicle_name}.'
                )
            elif action == 'reject':
                deposit.status = Deposit.STATUS_REJECTED
                deposit.approved_by = request.user
                deposit.approved_at = timezone.now()
                deposit.save()
                
                messages.warning(
                    request,
                    f'Deposit {deposit.or_code} rejected. No wallet update.'
                )
            
        except Deposit.DoesNotExist:
            messages.error(request, 'Deposit not found or already processed.')
        except Exception as e:
            messages.error(request, f'Error processing deposit: {str(e)}')
        
        return redirect('terminal:admin_approve_deposits')
    
    # GET request - show pending deposits
    pending_deposits = Deposit.objects.filter(
        status=Deposit.STATUS_PENDING
    ).select_related(
        'wallet__vehicle__assigned_driver',
        'created_by'
    ).order_by('-created_at')
    
    context = {
        'pending_deposits': pending_deposits,
    }
    return render(request, 'terminal/admin_approve_deposits.html', context)


# ===============================
# ✅ AJAX SEARCH ENDPOINTS
# ===============================

@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(lambda u: u.is_authenticated and u.role == 'treasurer')
def ajax_search_drivers(request):
    """AJAX endpoint to search drivers by name or vehicle info."""
    from django.http import JsonResponse
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search drivers by name, vehicle name, or license plate
    drivers = Driver.objects.prefetch_related('vehicles').filter(
        models.Q(first_name__icontains=query) |
        models.Q(last_name__icontains=query) |
        models.Q(vehicles__vehicle_name__icontains=query) |
        models.Q(vehicles__license_plate__icontains=query)
    ).distinct()[:10]
    
    results = []
    for driver in drivers:
        vehicle = driver.vehicles.first()
        if vehicle:
            results.append({
                'id': driver.id,
                'driver_name': f"{driver.first_name} {driver.last_name}",
                'vehicle_name': vehicle.vehicle_name,
                'license_plate': vehicle.license_plate,
                'license_number': driver.license_number or 'N/A',
                'wallet_balance': float(vehicle.wallet.balance)
            })
    
    return JsonResponse({'results': results})


@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(lambda u: u.is_authenticated and u.role == 'treasurer')
def ajax_get_system_settings(request):
    """AJAX endpoint to get system settings including minimum deposit."""
    from django.http import JsonResponse
    from terminal.models import SystemSettings
    
    settings = SystemSettings.get_solo()
    
    return JsonResponse({
        'min_deposit_amount': float(settings.min_deposit_amount),
        'terminal_fee': float(settings.terminal_fee)
    })


@login_required(login_url='/accounts/terminal-access/')
@user_passes_test(lambda u: u.is_authenticated and u.role == 'treasurer')
def ajax_validate_or_code(request):
    """AJAX endpoint to validate OR code uniqueness."""
    from django.http import JsonResponse
    
    or_code = request.GET.get('or_code', '').strip()
    
    if not or_code:
        return JsonResponse({'valid': False, 'message': 'OR Code is required'})
    
    exists = Deposit.objects.filter(or_code=or_code).exists()
    
    if exists:
        return JsonResponse({
            'valid': False,
            'message': f'OR Code "{or_code}" already exists. Please use a unique code.'
        })
    
    return JsonResponse({'valid': True, 'message': 'OR Code is available'})
