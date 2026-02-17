import calendar
import csv
import json
from collections import OrderedDict
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, F, Max, Q, Sum
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from pytz import timezone as pytz_timezone

# Shared helpers
from accounts.utils import is_staff_admin_or_admin, is_admin   # ✅ imported shared role checks
from terminal.shared_queue import (
    PASSENGER_DELETE_AFTER_MINUTES,
    apply_entry_log_maintenance,
    build_public_queue_entries,
)
from vehicles.models import Vehicle, Wallet, Deposit, Route, QueueHistory
from terminal.models import EntryLog, SystemSettings, TerminalActivity
from terminal.utils import format_route_display


QUICK_RANGE_LABELS = OrderedDict(
    [
        ("", "All history"),
        ("today", "Present day"),
        ("3days", "3 days after"),
        ("7days", "7 days after"),
        ("month", "Month after"),
    ]
)


def parse_preferred_date(value, tz):
    if not value:
        return timezone.localtime(timezone.now(), tz).date()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return timezone.localtime(timezone.now(), tz).date()


def make_datetime_from_date(date_value, tz):
    return timezone.make_aware(
        datetime(date_value.year, date_value.month, date_value.day, 0, 0, 0),
        tz,
    )


def build_export_filters(
    range_type,
    export_year,
    export_month,
    export_week,
    export_start,
    export_end,
    list_range,
    preferred_date_input,
    tz,
):
    start_filter = None
    end_filter = None
    try:
        if range_type == "year" and export_year:
            year_val = int(export_year)
            start_filter = timezone.make_aware(datetime(year_val, 1, 1), tz)
            end_filter = timezone.make_aware(datetime(year_val, 12, 31, 23, 59, 59), tz)
        elif range_type == "month" and export_month:
            year_val, month_val = map(int, export_month.split("-"))
            last_day = calendar.monthrange(year_val, month_val)[1]
            start_filter = timezone.make_aware(datetime(year_val, month_val, 1), tz)
            end_filter = timezone.make_aware(datetime(year_val, month_val, last_day, 23, 59, 59), tz)
        elif range_type == "week" and export_week:
            week_year, week_num = export_week.split("-W")
            week_start = datetime.fromisocalendar(int(week_year), int(week_num), 1)
            start_filter = timezone.make_aware(week_start, tz)
            end_filter = timezone.make_aware(week_start + timedelta(days=6, hours=23, minutes=59, seconds=59), tz)
        elif range_type == "custom":
            if export_start:
                start_date = datetime.strptime(export_start, "%Y-%m-%d")
                start_filter = timezone.make_aware(start_date, tz)
            if export_end:
                end_date = datetime.strptime(export_end, "%Y-%m-%d")
                end_filter = timezone.make_aware(end_date + timedelta(days=1) - timedelta(seconds=1), tz)
    except (ValueError, TypeError):
        return None, None

    if not range_type and list_range:
        span_days = {
            "today": 1,
            "3days": 3,
            "7days": 7,
            "month": 30,
        }.get(list_range)
        if span_days:
            base_date = parse_preferred_date(preferred_date_input, tz)
            day_start = make_datetime_from_date(base_date, tz)
            day_end = day_start + timedelta(days=span_days) - timedelta(seconds=1)
            start_filter = day_start
            end_filter = day_end

    return start_filter, end_filter


@login_required(login_url="accounts:login")
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def transactions_view(request):
    """
    Present Day Transactions View
    -----------------------------
    Shows ONLY transactions from TODAY (current date).
    Past transactions are archived and shown in past_transactions_view.
    """
    tz = timezone.get_current_timezone()
    today = timezone.localtime(timezone.now(), tz).date()
    
    # Get today's date boundaries
    today_start = timezone.make_aware(
        datetime(today.year, today.month, today.day, 0, 0, 0), tz
    )
    today_end = timezone.make_aware(
        datetime(today.year, today.month, today.day, 23, 59, 59), tz
    )

    # --------------------------------------------------
    # TODAY'S ACTIVITY ONLY
    # --------------------------------------------------
    activity_qs = (
        TerminalActivity.objects
        .select_related("vehicle__assigned_driver", "driver")
        .filter(timestamp__gte=today_start, timestamp__lte=today_end)
        .order_by("-timestamp")
    )

    # --------------------------------------------------
    # NORMALIZER
    # --------------------------------------------------
    def normalize(record):
        vehicle = record.vehicle
        driver = record.driver or getattr(vehicle, "assigned_driver", None)

        return {
            "timestamp": record.timestamp,
            "plate": getattr(vehicle, "license_plate", "—") if vehicle else "—",
            "driver": (
                f"{driver.first_name} {driver.last_name}"
                if driver else "N/A"
            ),
            "route": record.route_name or format_route_display(
                getattr(vehicle, "route", None)
            ),
            "event_label": record.get_event_type_display(),
            "action": record.event_type,
            "fee": record.fee_charged,
            "balance": record.wallet_balance_snapshot,
        }

    # --------------------------------------------------
    # TODAY'S RECORDS ONLY
    # --------------------------------------------------
    activity = [normalize(r) for r in activity_qs]

    # --------------------------------------------------
    # TODAY'S METRICS
    # --------------------------------------------------
    # Active queue count: vehicles currently in terminal (is_active=True, status=success)
    active_queue = EntryLog.objects.filter(is_active=True, status=EntryLog.STATUS_SUCCESS).count()

    # Today's entry logs count
    today_entry_logs = EntryLog.objects.filter(created_at__date=today).count()

    # Today's revenue only
    today_revenue = (
        TerminalActivity.objects
        .filter(
            event_type=TerminalActivity.EVENT_ENTRY,
            timestamp__gte=today_start,
            timestamp__lte=today_end
        )
        .aggregate(total=Sum("fee_charged"))["total"]
        or 0
    )

    # Today's entry count
    today_entries = (
        EntryLog.objects
        .filter(status=EntryLog.STATUS_SUCCESS, created_at__date=today)
        .count()
    )

    # Today's queue events
    today_queue_events = (
        QueueHistory.objects
        .filter(timestamp__gte=today_start, timestamp__lte=today_end)
        .count()
    )

    # --------------------------------------------------
    # RENDER
    # --------------------------------------------------
    context = {
        "activity": activity,
        "today_revenue": today_revenue,
        "today_entries": today_entries,
        "active_queue": active_queue,
        "today_entry_logs": today_entry_logs,
        "today_queue_events": today_queue_events,
        "activity_count": len(activity),
        "today_date": today.strftime("%B %d, %Y"),
        "today_date_short": today.strftime("%Y-%m-%d"),
    }

    return render(request, "terminal/transactions.html", context)

# ===============================
#   DEPOSIT ANALYTICS (Admin)
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_admin)
@never_cache
def deposit_analytics(request):
    """Admin-only analytics dashboard for deposits."""
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncDate

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    deposits = (
        Deposit.objects
        .select_related("wallet__vehicle__assigned_driver")
        .order_by("-created_at")
    )

    # Apply filters
    if start_date:
        deposits = deposits.filter(created_at__date__gte=start_date)
    if end_date:
        deposits = deposits.filter(created_at__date__lte=end_date)

    # Summary Metrics
    total_amount = deposits.aggregate(Sum("amount"))["amount__sum"] or 0
    total_transactions = deposits.count()
    unique_vehicles = deposits.values("wallet__vehicle").distinct().count()
    unique_drivers = deposits.values("wallet__vehicle__assigned_driver").distinct().count()

    # Top 5 Drivers
    top_drivers = (
        deposits.values("wallet__vehicle__assigned_driver__first_name",
                        "wallet__vehicle__assigned_driver__last_name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:5]
    )

    # Daily Deposits Chart
    daily_data = (
        deposits.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("amount"))
        .order_by("day")
    )

    chart_labels = [d["day"].strftime("%b %d") for d in daily_data]
    chart_data = [float(d["total"]) for d in daily_data]

    context = {
        "total_amount": total_amount,
        "total_transactions": total_transactions,
        "unique_vehicles": unique_vehicles,
        "unique_drivers": unique_drivers,
        "top_drivers": top_drivers,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "start_date": start_date or "",
        "end_date": end_date or "",
    }
    return render(request, "terminal/deposit_analytics.html", context)


# ===============================
#   DEPOSIT VS REVENUE COMPARISON (Admin)
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_admin)
@never_cache
def deposit_vs_revenue(request):
    """Compare total deposits vs terminal fees collected (EntryLog fees) per day."""
    from django.db.models import Sum
    from django.db.models.functions import TruncDate

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    deposits = Deposit.objects.all()
    logs = EntryLog.objects.filter(status=EntryLog.STATUS_SUCCESS)

    # Apply filters
    if start_date:
        deposits = deposits.filter(created_at__date__gte=start_date)
        logs = logs.filter(created_at__date__gte=start_date)
    if end_date:
        deposits = deposits.filter(created_at__date__lte=end_date)
        logs = logs.filter(created_at__date__lte=end_date)

    # Aggregate per day
    from collections import defaultdict
    daily_totals = defaultdict(lambda: {"deposit": 0, "revenue": 0})

    for d in (
        deposits.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("amount"))
    ):
        daily_totals[d["day"]]["deposit"] = float(d["total"])

    for l in (
        logs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("fee_charged"))
    ):
        daily_totals[l["day"]]["revenue"] = float(l["total"])

    # Sort and prepare for chart
    sorted_days = sorted(daily_totals.keys())
    chart_labels = [d.strftime("%b %d") for d in sorted_days]
    deposits_data = [daily_totals[d]["deposit"] for d in sorted_days]
    revenue_data = [daily_totals[d]["revenue"] for d in sorted_days]

    context = {
        "chart_labels": chart_labels,
        "deposits_data": deposits_data,
        "revenue_data": revenue_data,
        "start_date": start_date or "",
        "end_date": end_date or "",
    }
    return render(request, "terminal/deposit_vs_revenue.html", context)




# ===============================
#   TERMINAL QUEUE PAGE WRAPPER
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def terminal_queue(request):
    """Render the main terminal queue page (the page which will poll queue-data)."""
    # ensure auto-close/cleanup runs for admin pages too
    apply_entry_log_maintenance()
    return render(request, "terminal/terminal_queue.html")


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def tv_display_view(request, route_slug=None):
    """
    Terminal TV Display with partial page updates.
    - Shows boarding and departed vehicles only in main list
    - Queued vehicles shown as count badge
    - Uses WebSocket/Fetch for real-time updates without page reload
    - Preserves fullscreen state at all times
    """
    from terminal.services import QueueService

    ph_tz = pytz_timezone("Asia/Manila")
    all_routes = Route.objects.filter(active=True).order_by("origin", "destination")
    route_map = {slugify(r.name): r.name for r in all_routes}
    
    selected_route_name = None
    route_filter = None
    if route_slug:
        selected_route_name = route_map.get(route_slug.lower().strip("/"))
        # Get route ID for filtering
        for route in all_routes:
            if str(route) == selected_route_name:
                route_filter = route.id
                break

    # Get TV display state from service layer
    tv_state = QueueService.get_tv_display_state(route_filter=route_filter)

    # Ensure route_sections have visible_entries for template
    route_sections = tv_state.get("route_sections", [])
    for section in route_sections:
        if "visible_entries" not in section:
            section["visible_entries"] = [
                e for e in section.get("entries", [])
                if e.get("status") in ("Queued", "Boarding")
            ]
        section["slug"] = slugify(section.get("name", ""))
        section["history_events"] = tv_state.get("history", {}).get(section.get("name"), [])

    context = {
        "route_sections": json.dumps(route_sections),
        "all_routes": all_routes,
        "selected_route": selected_route_name,
        "selected_route_slug": slugify(selected_route_name) if selected_route_name else "",
        "current_time": timezone.localtime(timezone.now(), ph_tz).isoformat(),
        "countdown_duration": tv_state.get("countdown_duration", 30),
        "refresh_interval": tv_state.get("refresh_interval", 15),
        "departure_duration_minutes": tv_state.get("departure_duration_minutes", 30),
    }

    return render(request, "terminal/tv_display.html", context)

# ===============================
#   QUEUE DATA (AJAX endpoint)
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def queue_data(request):
    """AJAX endpoint for live queue refresh."""
    # maintenance
    apply_entry_log_maintenance()

    logs = (
        EntryLog.objects.filter(status=EntryLog.STATUS_SUCCESS, is_active=True)
        .select_related("vehicle__assigned_driver", "staff")
        .order_by("-created_at")[:20]
    )

    ph_tz = pytz_timezone("Asia/Manila")
    data = []
    for log in logs:
        v = log.vehicle
        d = v.assigned_driver if v else None
        # convert created_at to local time for display
        entry_local = timezone.localtime(log.created_at, ph_tz)
        data.append({
            "id": log.id,
            "vehicle_plate": getattr(v, "license_plate", "N/A") if v else "—",
            "vehicle_name": getattr(v, "vehicle_name", "—") if v else "—",
            "driver_name": f"{d.first_name} {d.last_name}" if d else "—",
            "fee": float(log.fee_charged),
            "staff": log.staff.username if log.staff else "—",
            "time": entry_local.strftime("%Y-%m-%d %I:%M %p"),
        })
    return JsonResponse({"entries": data})


# ===============================
#   SIMPLE QUEUE (TV)
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def simple_queue_view(request):
    # maintenance
    apply_entry_log_maintenance()

    settings = SystemSettings.get_solo()
    duration = getattr(settings, "departure_duration_minutes", 30)
    logs = EntryLog.objects.filter(is_active=True, status=EntryLog.STATUS_SUCCESS).select_related("vehicle__assigned_driver").order_by("-created_at")
    ph_tz = pytz_timezone("Asia/Manila")
    queue = []
    for log in logs:
        v = log.vehicle
        d = v.assigned_driver if v else None
        departure_time = log.created_at + timedelta(minutes=duration)
        queue.append({
            "plate": getattr(v, "license_plate", "N/A"),
            "driver": f"{d.first_name} {d.last_name}" if d else "N/A",
            "entry_time": timezone.localtime(log.created_at, ph_tz).strftime("%I:%M %p"),
            "departure_time": timezone.localtime(departure_time, ph_tz).strftime("%I:%M %p"),
        })
    context = {"queue": queue, "stay_duration": duration, "now": timezone.localtime(timezone.now(), ph_tz)}
    return render(request, "terminal/simple_queue.html", context)


# ===============================
#   MANAGE QUEUE
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def manage_queue(request):
    # maintenance
    apply_entry_log_maintenance()

    settings = SystemSettings.get_solo()
    duration = getattr(settings, "departure_duration_minutes", 30)
    logs = EntryLog.objects.filter(is_active=True, status=EntryLog.STATUS_SUCCESS).select_related("vehicle__assigned_driver","staff").order_by("-created_at")
    ph_tz = pytz_timezone("Asia/Manila")
    queue = []
    for log in logs:
        v = log.vehicle
        d = v.assigned_driver if v else None
        departure_time = log.created_at + timedelta(minutes=duration)
        queue.append({
            "id": log.id,
            "plate": getattr(v, "license_plate", "N/A"),
            "driver": f"{d.first_name} {d.last_name}" if d else "N/A",
            "entry_time": timezone.localtime(log.created_at, ph_tz).strftime("%I:%M %p"),
            "departure_time": timezone.localtime(departure_time, ph_tz).strftime("%I:%M %p"),
            "staff": log.staff.username if log.staff else "—",
        })
    return render(request, "terminal/manage_queue.html", {"queue": queue, "stay_duration": duration})

# ===============================
#   QR ENTRY / EXIT
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def qr_scan_entry(request):
    """Handles QR scan for both entry & departure validation with live balance feedback."""
    # Run maintenance on entry routes too so state is consistent when scanning
    apply_entry_log_maintenance()

    settings = SystemSettings.get_solo()
    entry_fee = settings.terminal_fee
    cooldown_minutes = settings.entry_cooldown_minutes
    min_deposit = settings.min_deposit_amount

    if request.method == "POST":
        qr_code = request.POST.get("qr_code", "").strip()
        if not qr_code:
            return JsonResponse({
                "status": "error",
                "message": "QR code is empty.",
                "balance": None
            })

        staff_user = request.user

        try:
            # 🔍 Validate vehicle
            vehicle = Vehicle.objects.filter(qr_value__iexact=qr_code).first()
            if not vehicle:
                return JsonResponse({
                    "status": "error",
                    "message": "❌ Invalid QR code.",
                    "balance": None
                })

            # ========================
            # 🚨 EXPIRY VALIDATION
            # ========================
            from datetime import date
            today = date.today()
            
            # Check vehicle registration expiry
            if vehicle.registration_expiry:
                if vehicle.registration_expiry < today:
                    return JsonResponse({
                        "status": "error",
                        "message": "❌ Vehicle registration expired. Please renew registration. Contact the terminal operator for assistance.",
                        "balance": None
                    })
            
            # Check driver license expiry
            driver = vehicle.assigned_driver
            if driver and driver.license_expiry:
                if driver.license_expiry < today:
                    return JsonResponse({
                        "status": "error",
                        "message": "❌ License expired. Please renew your license. Contact the terminal operator for assistance.",
                        "balance": None
                    })

            # 🏦 Get or create wallet
            wallet, _ = Wallet.objects.get_or_create(vehicle=vehicle)

            now = datetime.now(dt_timezone.utc)
            confirm_reset = str(request.POST.get("confirm_reset", "")).lower() in ("1", "true", "yes")

            # 🚗 Check if vehicle already inside terminal
            active_log = EntryLog.objects.filter(vehicle=vehicle, is_active=True).first()

            # ========================
            # 🔁 DEPARTURE LOGIC
            # ========================
            if active_log:
                if confirm_reset:
                    reset_message = (
                        f"Queue position reset confirmed by '{staff_user.username}'. "
                        f"Vehicle '{vehicle.license_plate}' moved to rejoin queue."
                    )
                    EntryLog.objects.filter(pk=active_log.pk).update(
                        created_at=now,
                        message=reset_message
                    )
                    return JsonResponse({
                        "status": "success",
                        "message": "🔁 Queue reset confirmed. Please proceed back to the line.",
                        "balance": float(wallet.balance)
                    })

                return JsonResponse({
                    "status": "queued",
                    "message": (
                        "⚠️ You're already queued. Scan again to reset your position "
                        "if you missed your turn or stepped out briefly."
                    ),
                    "balance": float(wallet.balance)
                })

            # ========================
            # 🚘 ENTRY LOGIC
            # ========================
            recent_entry = EntryLog.objects.filter(
                vehicle=vehicle,
                status=EntryLog.STATUS_SUCCESS
            ).order_by("-created_at").first()

            if recent_entry and (now - recent_entry.created_at) < timedelta(minutes=cooldown_minutes):
                return JsonResponse({
                    "status": "error",
                    "message": "⏳ Please wait before re-entry.",
                    "balance": float(wallet.balance)
                })

            if wallet.balance < min_deposit:
                return JsonResponse({
                    "status": "error",
                    "message": f"⚠️ Minimum ₱{min_deposit} required before entry.",
                    "balance": float(wallet.balance)
                })

            if wallet.balance >= entry_fee:
                wallet.balance -= entry_fee
                wallet.save()

                EntryLog.objects.create(
                    vehicle=vehicle,
                    staff=staff_user,
                    fee_charged=entry_fee,
                    wallet_balance_snapshot=wallet.balance,
                    status=EntryLog.STATUS_SUCCESS,
                    message=f"Vehicle '{vehicle.license_plate}' entered terminal."
                )
                if vehicle:
                    departure_snapshot = timezone.now() + timedelta(
                        minutes=getattr(settings, "departure_duration_minutes", 30)
                    )
                    QueueHistory.objects.create(
                        vehicle=vehicle,
                        driver=getattr(vehicle, "assigned_driver", None),
                        action="enter",
                        departure_time_snapshot=departure_snapshot,
                        wallet_balance_snapshot=wallet.balance,
                        fee_charged=entry_fee,
                    )

                return JsonResponse({
                    "status": "success",
                    "message": f"🚗 {vehicle.license_plate} entered terminal.",
                    "balance": float(wallet.balance)
                })
            else:
                EntryLog.objects.create(
                    vehicle=vehicle,
                    staff=staff_user,
                    fee_charged=entry_fee,
                    wallet_balance_snapshot=wallet.balance,
                    status=EntryLog.STATUS_INSUFFICIENT,
                    message=f"Insufficient balance for '{vehicle.license_plate}'."
                )

                return JsonResponse({
                    "status": "error",
                    "message": f"❌ Insufficient balance for {vehicle.license_plate}.",
                    "balance": float(wallet.balance)
                })

        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "balance": None
            })

    # GET request → render scan page
    context = {
        "terminal_fee": entry_fee,
        "min_deposit": min_deposit,
        "cooldown": cooldown_minutes,
    }
    return render(request, "terminal/qr_scan_entry.html", context)


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def qr_exit_validation(request):
    """Handles QR scan for exit validation only."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method."})

    qr_code = request.POST.get("qr_code", "").strip()
    if not qr_code:
        return JsonResponse({"status": "error", "message": "QR missing."})

    try:
        vehicle = Vehicle.objects.filter(qr_value__iexact=qr_code).first()
        if not vehicle:
            return JsonResponse({"status": "error", "message": "❌ No vehicle found."})

        # Validate that vehicle has an active entry record
        active_log = EntryLog.objects.filter(vehicle=vehicle, is_active=True).first()
        if not active_log:
            return JsonResponse({
                "status": "error", 
                "message": f"⚠️ {vehicle.license_plate} not inside terminal. No active entry found."
            })

        # Mark as exited
        active_log.is_active = False
        active_log.departed_at = timezone.now()
        active_log.save(update_fields=["is_active", "departed_at"])
        
        # Create exit queue history
        vehicle = active_log.vehicle
        if vehicle:
            QueueHistory.objects.create(
                vehicle=vehicle,
                driver=getattr(vehicle, "assigned_driver", None),
                action="exit",
                departure_time_snapshot=active_log.departed_at,
                wallet_balance_snapshot=getattr(getattr(vehicle, "wallet", None), "balance", None),
                fee_charged=Decimal("0.00"),
            )

        return JsonResponse({
            "status": "success",
            "message": f"✅ {vehicle.license_plate} successfully exited terminal."
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        })
                fee_charged=None,
            )
        return JsonResponse({"status": "success", "message": f"✅ {vehicle.license_plate} departed."})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def qr_exit_page(request):
    return render(request, "terminal/qr_exit_validation.html")


# ===============================
#   SYSTEM SETTINGS (Admin only)
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_admin)
@never_cache
def system_settings(request):
    """Admin-only configuration page with seat capacity limits and queue display settings."""
    settings = SystemSettings.get_solo()

    class SettingsForm(forms.ModelForm):
        class Meta:
            model = SystemSettings
            fields = [
                'terminal_fee',
                'min_deposit_amount',
                'entry_cooldown_minutes',
                'departure_duration_minutes',
                'countdown_duration_seconds',
                'queue_refresh_interval_seconds',
                'jeepney_max_seats',
                'van_max_seats',
                'bus_max_seats',
            ]
            widgets = {
                'terminal_fee': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
                'min_deposit_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
                'entry_cooldown_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
                'departure_duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
                'countdown_duration_seconds': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '300'}),
                'queue_refresh_interval_seconds': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '120'}),
                'jeepney_max_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
                'van_max_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
                'bus_max_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            }

    form = SettingsForm(request.POST or None, instance=settings)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "✅ System settings updated successfully!")
            return redirect('terminal:system_settings')
        else:
            messages.error(request, "❌ Please correct the errors below.")

    return render(request, "terminal/system_settings.html", {"form": form})


# ===============================
#   ARCHIVE HELPER FOR PAST TRANSACTIONS
# ===============================
def _archive_past_activities(archive_date, tz):
    """
    Archive TerminalActivity records from a specific date into Transaction model.
    This is called when viewing past transactions to ensure records are archived.
    
    Args:
        archive_date: The date to archive (typically yesterday)
        tz: Timezone to use for date boundaries
    """
    from terminal.models import Transaction
    
    # Get date boundaries
    date_start = timezone.make_aware(
        datetime(archive_date.year, archive_date.month, archive_date.day, 0, 0, 0), tz
    )
    date_end = timezone.make_aware(
        datetime(archive_date.year, archive_date.month, archive_date.day, 23, 59, 59), tz
    )
    
    # Get entry activities from that date that haven't been archived yet
    entry_activities = (
        TerminalActivity.objects
        .filter(
            event_type=TerminalActivity.EVENT_ENTRY,
            timestamp__gte=date_start,
            timestamp__lte=date_end,
        )
        .select_related("vehicle", "driver", "vehicle__route", "entry_log")
    )
    
    # Create Transaction records for each activity if not already exists
    for activity in entry_activities:
        # Check if already archived
        if activity.entry_log_id:
            exists = Transaction.objects.filter(entry_log_id=activity.entry_log_id).exists()
            if exists:
                continue
        
        # Also check by timestamp and vehicle to avoid duplicates
        vehicle = activity.vehicle
        exists_by_match = Transaction.objects.filter(
            vehicle=vehicle,
            entry_timestamp__gte=date_start,
            entry_timestamp__lte=date_end,
            fee_charged=activity.fee_charged or 0,
        ).exists()
        
        if exists_by_match:
            continue
        
        # Find corresponding exit activity
        exit_activity = (
            TerminalActivity.objects
            .filter(
                vehicle=vehicle,
                event_type=TerminalActivity.EVENT_EXIT,
                timestamp__gt=activity.timestamp,
            )
            .order_by("timestamp")
            .first()
        )
        
        exit_timestamp = exit_activity.timestamp if exit_activity else None
        
        driver = activity.driver or (vehicle.assigned_driver if vehicle else None)
        route = vehicle.route if vehicle else None
        
        Transaction.objects.create(
            vehicle=vehicle,
            driver=driver,
            entry_log=activity.entry_log,
            vehicle_plate=getattr(vehicle, "license_plate", "—") if vehicle else "—",
            driver_name=f"{driver.first_name} {driver.last_name}" if driver else "N/A",
            route_name=activity.route_name or (f"{route.origin} → {route.destination}" if route else "Unassigned"),
            entry_timestamp=activity.timestamp,
            exit_timestamp=exit_timestamp,
            fee_charged=activity.fee_charged or 0,
            wallet_balance_snapshot=activity.wallet_balance_snapshot,
            transaction_date=archive_date,
            transaction_year=archive_date.year,
            transaction_month=archive_date.month,
            transaction_day=archive_date.day,
            is_revenue_counted=True,
        )


# ===============================
#   PAST TRANSACTIONS (with date filtering & CSV export)
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def past_transactions_view(request):
    """
    Past Transactions View (Archived Records)
    -----------------------------------------
    Shows ONLY transactions from BEFORE today (yesterday and earlier).
    Today's transactions are shown in transactions_view.
    
    Also archives yesterday's TerminalActivity records into Transaction model.
    """
    from terminal.models import Transaction
    from terminal.services import TransactionService

    tz = timezone.get_current_timezone()
    today = timezone.localtime(timezone.now(), tz).date()
    yesterday = today - timedelta(days=1)

    # --------------------------------------------------
    # ARCHIVE YESTERDAY'S RECORDS (bulk archive)
    # --------------------------------------------------
    _archive_past_activities(yesterday, tz)

    # Get filter parameters
    start_date_str = request.GET.get("start_date", "")
    end_date_str = request.GET.get("end_date", "")
    export_action = request.GET.get("export", "")

    # Parse dates
    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = None

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = None

    # --------------------------------------------------
    # QUERY PAST TRANSACTIONS ONLY (before today)
    # --------------------------------------------------
    transactions_qs = (
        Transaction.objects
        .filter(transaction_date__lt=today)  # ONLY records BEFORE today
        .order_by("-entry_timestamp")
    )

    # Apply date filters if provided
    if start_date:
        transactions_qs = transactions_qs.filter(transaction_date__gte=start_date)
    if end_date:
        # Ensure end_date is still before today
        if end_date >= today:
            end_date = yesterday
        transactions_qs = transactions_qs.filter(transaction_date__lte=end_date)

    # CSV Export
    if export_action == "csv":
        csv_content = TransactionService.export_transactions_csv(transactions_qs)

        label = "past"
        if start_date and end_date:
            label = f"{start_date}_to_{end_date}"
        elif start_date:
            label = f"from_{start_date}"
        elif end_date:
            label = f"until_{end_date}"

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="past_transactions_{label}.csv"'
        response.write(csv_content)
        return response

    # Calculate summary metrics for filtered past records
    total_revenue = transactions_qs.filter(is_revenue_counted=True).aggregate(
        total=Sum("fee_charged")
    )["total"] or 0
    total_transactions = transactions_qs.count()

    # Yesterday's revenue specifically
    yesterday_revenue = (
        Transaction.objects
        .filter(transaction_date=yesterday, is_revenue_counted=True)
        .aggregate(total=Sum("fee_charged"))["total"]
        or 0
    )

    # Paginate for display (limit to 200)
    transactions = list(transactions_qs[:200])

    context = {
        "transactions": transactions,
        "total_revenue": total_revenue,
        "total_transactions": total_transactions,
        "yesterday_revenue": yesterday_revenue,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "today": today.strftime("%Y-%m-%d"),
        "yesterday": yesterday.strftime("%Y-%m-%d"),
        "yesterday_display": yesterday.strftime("%B %d, %Y"),
    }

    return render(request, "terminal/past_transactions.html", context)


# ===============================
#   MARK DEPARTED / UPDATE TIME / HISTORY
# ===============================
@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def mark_departed(request, entry_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."})
    try:
        log = get_object_or_404(EntryLog, id=entry_id, is_active=True)
        log.is_active = False
        log.departed_at = timezone.now()
        log.save(update_fields=["is_active", "departed_at"])
        return JsonResponse({"success": True, "message": f"✅ {log.vehicle.license_plate} marked departed."})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def update_departure_time(request, entry_id):
    from django.utils.dateparse import parse_datetime
    import json
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request."})
    try:
        log = get_object_or_404(EntryLog, id=entry_id, is_active=True)
        data = json.loads(request.body)
        new_time = parse_datetime(data.get("departure_time", ""))
        if not new_time:
            return JsonResponse({"success": False, "message": "Invalid datetime."})
        log.departed_at = timezone.make_aware(new_time)
        log.save(update_fields=["departed_at"])
        return JsonResponse({"success": True, "message": f"Updated departure for {log.vehicle.license_plate}."})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@never_cache
def queue_history(request):
    return redirect('terminal:transactions')


@login_required(login_url='accounts:login')
@user_passes_test(is_admin)
@never_cache
def manage_routes(request):
    """Admin-only page for managing routes and viewing analytics."""
    from django.db.models import Count, Sum

    # --- ROUTE CRUD HANDLING ---
    if request.method == "POST":
        action = request.POST.get("action")
        route_id = request.POST.get("route_id")
        name = request.POST.get("name", "").strip()
        origin = request.POST.get("origin", "").strip()
        destination = request.POST.get("destination", "").strip()
        base_fare = request.POST.get("base_fare", "").strip()
        active = bool(request.POST.get("active"))

        # Validation
        if not origin or not destination:
            messages.error(request, "⚠️ Both origin and destination are required.")
            return redirect("terminal:manage_routes")

        try:
            base_fare = Decimal(base_fare) if base_fare else Decimal("0.00")
        except Exception:
            base_fare = Decimal("0.00")

        # Prevent duplicate routes
        existing = Route.objects.filter(
            origin__iexact=origin,
            destination__iexact=destination
        ).exclude(id=route_id).exists()
        if existing:
            messages.error(request, f"⚠️ Route {origin} → {destination} already exists.")
            return redirect("terminal:manage_routes")

        if action == "add":
            Route.objects.create(
                name=name or f"{origin} - {destination}",
                origin=origin,
                destination=destination,
                base_fare=base_fare,
                active=active,
            )
            messages.success(request, f"✅ Route {origin} → {destination} added successfully!")

        elif action == "edit" and route_id:
            route = get_object_or_404(Route, id=route_id)
            route.name = name or f"{origin} - {destination}"
            route.origin = origin
            route.destination = destination
            route.base_fare = base_fare
            route.active = active
            route.save()
            messages.success(request, f"✅ Route {origin} → {destination} updated successfully!")

        elif action == "delete" and route_id:
            route = get_object_or_404(Route, id=route_id)
            route_name = f"{route.origin} → {route.destination}"
            route.delete()
            messages.success(request, f"🗑️ Route {route_name} deleted successfully!")

        else:
            messages.warning(request, "⚠️ Invalid action or missing route ID.")

        return redirect("terminal:manage_routes")

    # --- ANALYTICS SECTION ---
    routes = Route.objects.all().order_by('origin', 'destination')

    route_stats = (
        EntryLog.objects
        .filter(vehicle__route__isnull=False)
        .values('vehicle__route__id', 'vehicle__route__origin', 'vehicle__route__destination')
        .annotate(
            total_trips=Count('id'),
            total_fees=Sum('fee_charged')
        )
        .order_by('-total_trips')
    )

    total_trips = sum(item['total_trips'] for item in route_stats)
    total_fees = sum(item['total_fees'] or 0 for item in route_stats)
    active_routes = routes.filter(active=True).count()
    top_route = route_stats[0] if route_stats else None

    # --- Chart.js Data ---
    chart_labels = [f"{r['vehicle__route__origin']} → {r['vehicle__route__destination']}" for r in route_stats]
    chart_data = [r['total_trips'] for r in route_stats]

    context = {
        "routes": routes,
        "total_trips": total_trips,
        "total_fees": total_fees,
        "active_routes": active_routes,
        "top_route": top_route,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
    }

    return render(request, "terminal/manage_routes.html", context)


@login_required(login_url='accounts:login')
@user_passes_test(is_admin)
@never_cache
def system_and_routes(request):
    """Unified admin page for system settings and route management."""
    from django.db.models import Count, Sum
    
    settings = SystemSettings.get_solo()

    # Settings Form
    class SettingsForm(forms.ModelForm):
        class Meta:
            model = SystemSettings
            fields = [
                'terminal_fee',
                'min_deposit_amount',
                'entry_cooldown_minutes',
                'departure_duration_minutes',
                'countdown_duration_seconds',
                'queue_refresh_interval_seconds',
                'jeepney_max_seats',
                'van_max_seats',
                'bus_max_seats',
            ]
            widgets = {
                'terminal_fee': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
                'min_deposit_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
                'entry_cooldown_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
                'departure_duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
                'countdown_duration_seconds': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '300'}),
                'queue_refresh_interval_seconds': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '120'}),
                'jeepney_max_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
                'van_max_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
                'bus_max_seats': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            }

    # Handle POST requests
    if request.method == "POST":
        action = request.POST.get("action")
        
        # ROUTE ACTIONS
        if action in ["add", "edit", "delete"]:
            route_id = request.POST.get("route_id")
            name = request.POST.get("name", "").strip()
            origin = request.POST.get("origin", "").strip()
            destination = request.POST.get("destination", "").strip()
            base_fare = request.POST.get("base_fare", "").strip()
            active = bool(request.POST.get("active"))

            if not origin or not destination:
                messages.error(request, "⚠️ Both origin and destination are required.")
                return redirect("terminal:system_and_routes")

            try:
                base_fare = Decimal(base_fare) if base_fare else Decimal("0.00")
            except Exception:
                base_fare = Decimal("0.00")

            existing = Route.objects.filter(
                origin__iexact=origin,
                destination__iexact=destination
            ).exclude(id=route_id).exists()
            if existing and action != "delete":
                messages.error(request, f"⚠️ Route {origin} → {destination} already exists.")
                return redirect("terminal:system_and_routes")

            if action == "add":
                Route.objects.create(
                    name=name or f"{origin} - {destination}",
                    origin=origin,
                    destination=destination,
                    base_fare=base_fare,
                    active=active,
                )
                messages.success(request, f"✅ Route {origin} → {destination} added successfully!")

            elif action == "edit" and route_id:
                route = get_object_or_404(Route, id=route_id)
                route.name = name or f"{origin} - {destination}"
                route.origin = origin
                route.destination = destination
                route.base_fare = base_fare
                route.active = active
                route.save()
                messages.success(request, f"✅ Route {origin} → {destination} updated successfully!")

            elif action == "delete" and route_id:
                route = get_object_or_404(Route, id=route_id)
                route_name = f"{route.origin} → {route.destination}"
                route.delete()
                messages.success(request, f"🗑️ Route {route_name} deleted successfully!")

            return redirect("terminal:system_and_routes")
        
        # SETTINGS SAVE
        else:
            form = SettingsForm(request.POST, instance=settings)
            if form.is_valid():
                form.save()
                messages.success(request, "✅ System settings updated successfully!")
                return redirect('terminal:system_and_routes')
            else:
                messages.error(request, "❌ Please correct the errors below.")
    else:
        form = SettingsForm(instance=settings)

    # Route Analytics
    routes = Route.objects.all().order_by('origin', 'destination')
    route_stats = (
        EntryLog.objects
        .filter(vehicle__route__isnull=False)
        .values('vehicle__route__id', 'vehicle__route__origin', 'vehicle__route__destination')
        .annotate(
            total_trips=Count('id'),
            total_fees=Sum('fee_charged')
        )
        .order_by('-total_trips')
    )

    total_trips = sum(item['total_trips'] for item in route_stats)
    total_fees = sum(item['total_fees'] or 0 for item in route_stats)
    active_routes = routes.filter(active=True).count()
    top_route = route_stats[0] if route_stats else None

    chart_labels = json.dumps([f"{r['vehicle__route__origin']} → {r['vehicle__route__destination']}" for r in route_stats])
    chart_data = json.dumps([r['total_trips'] for r in route_stats])

    context = {
        "form": form,
        "routes": routes,
        "total_trips": total_trips,
        "total_fees": total_fees,
        "active_routes": active_routes,
        "top_route": top_route,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
    }

    return render(request, "terminal/system_and_routes.html", context)



# ===============================
#   AJAX ADD DEPOSIT (New)
# ===============================
from django.views.decorators.csrf import csrf_exempt

@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@csrf_exempt
def ajax_add_deposit(request):
    """AJAX-based deposit submission (no page reload)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})

    vehicle_id = request.POST.get('vehicle_id')
    amount = request.POST.get('amount')

    if not vehicle_id or not amount:
        return JsonResponse({'success': False, 'message': 'Missing fields.'})

    try:
        vehicle = Vehicle.objects.get(pk=vehicle_id)
        wallet, _ = Wallet.objects.get_or_create(vehicle=vehicle)
        amt = Decimal(amount)

        if amt <= 0:
            return JsonResponse({'success': False, 'message': 'Amount must be greater than zero.'})

        deposit = Deposit.objects.create(wallet=wallet, amount=amt)

        return JsonResponse({
            'success': True,
            'message': f"✅ Deposit of ₱{amt} for {vehicle.license_plate} recorded!",
            'deposit': {
                'reference': deposit.reference_number,
                'driver': f"{vehicle.assigned_driver.last_name}, {vehicle.assigned_driver.first_name}",
                'vehicle': vehicle.license_plate,
                'amount': float(deposit.amount),
                'date': deposit.created_at.strftime("%b %d, %Y %I:%M %p")
            }
        })
    except Vehicle.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Vehicle not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required(login_url='accounts:login')
@user_passes_test(is_staff_admin_or_admin)
@csrf_exempt
def ajax_get_wallet_balance(request):
    """Return current wallet balance for a selected vehicle."""
    vehicle_id = request.GET.get('vehicle_id')
    if not vehicle_id:
        return JsonResponse({'success': False, 'message': 'Vehicle ID missing.'})

    try:
        vehicle = Vehicle.objects.get(pk=vehicle_id)
        wallet, _ = Wallet.objects.get_or_create(vehicle=vehicle)
        return JsonResponse({
            'success': True,
            'balance': float(wallet.balance),
            'vehicle': vehicle.license_plate
        })
    except Vehicle.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Vehicle not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
