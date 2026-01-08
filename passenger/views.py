# passenger/views.py
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from terminal.models import EntryLog, SystemSettings
from vehicles.models import Vehicle, Route
from django.http import JsonResponse
from django.db.models import Q

# Passenger-specific delete window (minutes) for quick hide on public view
PASSENGER_DELETE_AFTER_MINUTES = 10
DEPARTED_VISIBLE_MINUTES = 5


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

    # 1) Auto-close active entries where created_at + departure_duration <= now
    cutoff = now - timedelta(minutes=departure_duration)
    active_qs = EntryLog.objects.filter(is_active=True, created_at__lte=cutoff)
    if active_qs.exists():
        active_qs.update(is_active=False, departed_at=now)

    # 2) Delete departed/non-active entries older than PASSENGER_DELETE_AFTER_MINUTES
    delete_cutoff = now - timedelta(minutes=PASSENGER_DELETE_AFTER_MINUTES)
    old_qs = EntryLog.objects.filter(created_at__lt=delete_cutoff).filter(
        Q(is_active=False) | Q(departed_at__isnull=False)
    )
    if old_qs.exists():
        old_qs.delete()


def home(request):
    return render(request, 'passenger/home.html')


def announcement(request):
    return render(request, 'passenger/announcement.html')

def contact(request):
    return render(request, 'passenger/contact.html')


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

    keep_departed_for = timedelta(minutes=DEPARTED_VISIBLE_MINUTES)
    departed_cutoff = now - keep_departed_for

    queue_entries = (
        EntryLog.objects
        .select_related('vehicle', 'vehicle__assigned_driver', 'vehicle__route')
        .filter(
            Q(is_active=True, created_at__date=timezone.localtime(now).date()) |
            Q(departed_at__gte=departed_cutoff)
        )
        .order_by('created_at')
    )

    if route_filter and route_filter != 'all':
        queue_entries = queue_entries.filter(vehicle__route_id=route_filter)

    entries = []

    for log in queue_entries:
        v = log.vehicle
        d = v.assigned_driver if v else None

        # ⏱ Base time for countdown
        base_time = log.departed_at if not log.is_active and log.departed_at else log.created_at
        expiry_time = base_time + timedelta(minutes=departure_duration)

        remaining_seconds = int((expiry_time - now).total_seconds())

        entries.append({
            "id": log.id,
            "vehicle": v,
            "driver": d,
            "route": getattr(v.route, "name", None) if v and v.route else None,

            "entry_time": timezone.localtime(log.created_at),
            "departed_at": timezone.localtime(log.departed_at) if log.departed_at else None,
            "expiry_time": timezone.localtime(expiry_time),

            "remaining_seconds": max(remaining_seconds, 0),
            "is_expired": remaining_seconds <= 0,
            "is_active": log.is_active,
        })

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

    ten_mins_ago = now - timedelta(minutes=10)
    route_filter = request.GET.get("route", "all")

    queue_entries = (
        EntryLog.objects.select_related("vehicle", "vehicle__assigned_driver", "vehicle__route")
        .filter(
            status=EntryLog.STATUS_SUCCESS,
            created_at__gte=ten_mins_ago - timedelta(minutes=departure_duration)
        )
        .order_by("created_at")
    )

    if route_filter and route_filter != "all":
        queue_entries = queue_entries.filter(vehicle__route_id=route_filter)

    data = []
    for q in queue_entries:
        v = q.vehicle
        if q.is_active and timezone.localtime(q.created_at).date() != timezone.localtime(now).date():
            continue

        departure_time = q.created_at + timedelta(minutes=departure_duration)
        is_boarding = q.is_active
        is_departed_recently = (
            not q.is_active and q.departed_at and
            (now - q.departed_at <= timedelta(minutes=PASSENGER_DELETE_AFTER_MINUTES))
        )

        if is_boarding or is_departed_recently:
            data.append({
                "plate": v.license_plate if v else "—",
                "driver": f"{v.assigned_driver.first_name} {v.assigned_driver.last_name}"
                          if v and v.assigned_driver else "—",
                "route": f"{v.route.origin} → {v.route.destination}" if v and v.route else "—",
                "status": "Boarding" if is_boarding else "Departed",
                "departure": timezone.localtime(departure_time).strftime("%Y-%m-%d %H:%M:%S"),
            })

    return JsonResponse({"entries": data})
