# passenger/views.py
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from terminal.models import EntryLog, SystemSettings
from vehicles.models import Vehicle, Route
from django.http import JsonResponse
from django.db.models import Q
from collections import OrderedDict

# Passenger-specific delete window (minutes) for quick hide on public view
PASSENGER_DELETE_AFTER_MINUTES = 1
DEPARTED_VISIBLE_MINUTES = 1


def _maintenance_task(now=None):
    """
    Run light, idempotent maintenance:
    - Auto-close active entries whose created_at + admin_duration <= now.
    - Delete departed/non-active entries older than PASSENGER_DELETE_AFTER_MINUTES.
    """
    now = now or timezone.now()

    # load admin-config
    settings = SystemSettings.get_solo()
    departure_duration = int(getattr(settings, "departure_duration_minutes", 30))
    departed_cutoff = now - timedelta(minutes=DEPARTED_VISIBLE_MINUTES)

    # 1) Auto-close active entries where created_at + departure_duration <= now
    cutoff = now - timedelta(minutes=departure_duration)
    active_qs = EntryLog.objects.filter(is_active=True, created_at__lte=cutoff)
    if active_qs.exists():
        active_qs.update(is_active=False, departed_at=now)

    # 2) Delete departed/non-active entries older than PASSENGER_DELETE_AFTER_MINUTES
    delete_cutoff = now - timedelta(minutes=PASSENGER_DELETE_AFTER_MINUTES)
    old_qs = EntryLog.objects.filter(
        departed_at__lt=delete_cutoff
    )
    if old_qs.exists():
        old_qs.delete()


def home(request):
    return render(request, 'passenger/home.html')


def announcement(request):
    return render(request, 'passenger/announcement.html')

def contact(request):
    return render(request, 'passenger/contact.html')


def _build_public_queue_entries(queue_logs, now, departure_duration, departed_cutoff):
    route_groups = OrderedDict()
    for log in queue_logs:
        vehicle = getattr(log, "vehicle", None)
        route = getattr(vehicle, "route", None)
        route_key = route.id if route else None
        if route_key not in route_groups:
            route_name = (
                f"{route.origin} → {route.destination}" if route else "Unassigned"
            )
            route_groups[route_key] = {"route_name": route_name, "logs": []}
        route_groups[route_key]["logs"].append(log)

    entries = []
    for group in route_groups.values():
        route_name = group["route_name"]
        boarding_log = next((log for log in group["logs"] if log.is_active), None)

        for log in group["logs"]:
            if log.is_active and log == boarding_log:
                status = "Boarding"
            elif log.is_active:
                status = "Queued"
            elif log.departed_at and log.departed_at >= departed_cutoff:
                status = "Departed"
            else:
                continue

            expiry_timestamp = None
            if status == "Boarding":
                boarding_start = log.boarding_started_at
                if not boarding_start:
                    boarding_start = now
                    EntryLog.objects.filter(pk=log.pk).update(boarding_started_at=boarding_start)
                expiry = boarding_start + timedelta(minutes=departure_duration)
                expiry_timestamp = int(expiry.timestamp())

            vehicle = getattr(log, "vehicle", None)
            driver = getattr(vehicle, "assigned_driver", None)
            entry_display = timezone.localtime(log.created_at).strftime("%b %d, %Y %I:%M %p")
            entry_numeric = timezone.localtime(log.created_at).strftime("%b %d, %Y %I:%M %p")
            departure_time = log.created_at + timedelta(minutes=departure_duration)
            departure_display = timezone.localtime(departure_time).strftime("%b %d, %Y %I:%M %p")
            entries.append({
                "id": log.id,
                "entry_time_display": entry_display,
                "entry_time_numeric": entry_numeric,
                "departure_time_display": departure_display,
                "vehicle_plate": vehicle.license_plate if vehicle else "—",
                "route": route_name,
                "driver_name": f"{driver.first_name} {driver.last_name}" if driver else "N/A",
                "status": status,
                "countdown_active": status == "Boarding",
                "expiry_timestamp": expiry_timestamp,
            })
    return entries


def public_queue_view(request):
    """
    Public Passenger View:
    - Shows active vehicles created today
    - Shows recently departed vehicles
    - Supports real-time countdown (HH:MM)
    """

    now = timezone.now()
    _maintenance_task(now=now)

    route_filter = request.GET.get('route')
    settings = SystemSettings.get_solo()
    departure_duration = int(getattr(settings, "departure_duration_minutes", 30))
    departed_cutoff = now - timedelta(minutes=DEPARTED_VISIBLE_MINUTES)

    queue_logs = (
        EntryLog.objects
        .select_related('vehicle', 'vehicle__assigned_driver', 'vehicle__route')
        .filter(
            status=EntryLog.STATUS_SUCCESS
        )
        .filter(
            Q(is_active=True) | Q(departed_at__gte=departed_cutoff)
        )
        .order_by('created_at')
    )

    if route_filter and route_filter != 'all':
        queue_logs = queue_logs.filter(vehicle__route_id=route_filter)

    from collections import OrderedDict
    route_groups = OrderedDict()
    for log in queue_logs:
        vehicle = getattr(log, "vehicle", None)
        route = getattr(vehicle, "route", None)
        route_key = route.id if route else None
        if route_key not in route_groups:
            route_groups[route_key] = {
                "route_name": (
                    f"{route.origin} → {route.destination}" if route else "Unassigned"
                ),
                "logs": []
            }
        route_groups[route_key]["logs"].append(log)

    entries = _build_public_queue_entries(queue_logs, now, departure_duration, departed_cutoff)

    routes = Route.objects.filter(active=True).order_by("origin", "destination")

    context = {
        "queue_entries": entries,
        "routes": routes,
        "selected_route": route_filter,
        "departure_duration_minutes": departure_duration,
        "server_now": timezone.localtime(now),
    }

    return render(request, 'passenger/public_queue.html', context)


def public_queue_data(request):
    """AJAX endpoint for live smooth refresh."""
    now = timezone.now()
    _maintenance_task(now=now)

    settings = SystemSettings.get_solo()
    departure_duration = int(getattr(settings, "departure_duration_minutes", 30))

    route_filter = request.GET.get("route", "all")

    queue_logs = (
        EntryLog.objects
        .select_related("vehicle", "vehicle__assigned_driver", "vehicle__route")
        .filter(
            status=EntryLog.STATUS_SUCCESS
        )
        .filter(
            Q(is_active=True) | Q(departed_at__gte=departed_cutoff)
        )
        .order_by("created_at")
    )

    if route_filter and route_filter != "all":
        queue_logs = queue_logs.filter(vehicle__route_id=route_filter)

    entries = _build_public_queue_entries(queue_logs, now, departure_duration, departed_cutoff)

    return JsonResponse({
        "entries": entries,
        "server_time": int(now.timestamp()),
    })
