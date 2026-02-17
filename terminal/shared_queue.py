from collections import OrderedDict
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from terminal.models import EntryLog, SystemSettings

DEFAULT_DELETE_AFTER_MINUTES = 10
PASSENGER_DELETE_AFTER_MINUTES = 1
DEPARTED_VISIBLE_MINUTES = 1


def apply_entry_log_maintenance(now=None, delete_after_minutes=None):
    """Unified entry log maintenance (auto close + expunge)."""
    now = now or timezone.now()

    settings = SystemSettings.get_solo()
    departure_duration = int(getattr(settings, "departure_duration_minutes", 30))

    cutoff = now - timedelta(minutes=departure_duration)
    active_to_close = EntryLog.objects.filter(is_active=True, created_at__lte=cutoff)
    if active_to_close.exists():
        active_to_close.update(is_active=False, departed_at=now)

    delete_after_minutes = delete_after_minutes if delete_after_minutes is not None else DEFAULT_DELETE_AFTER_MINUTES
    delete_cutoff = now - timedelta(minutes=int(delete_after_minutes))
    old_qs = EntryLog.objects.filter(created_at__lt=delete_cutoff).filter(
        Q(is_active=False) | Q(departed_at__isnull=False)
    )
    if old_qs.exists():
        old_qs.delete()

    departed_cutoff = now - timedelta(minutes=DEPARTED_VISIBLE_MINUTES)

    return now, departure_duration, departed_cutoff


def build_public_queue_entries(queue_logs, now, departure_duration, departed_cutoff):
    """Return structured queue entries grouped by route for both public and terminal views."""
    route_groups = OrderedDict()
    for log in queue_logs:
        vehicle = getattr(log, "vehicle", None)
        route = getattr(vehicle, "route", None)
        route_key = route.id if route else None
        if route_key not in route_groups:
            route_name = f"{route.origin} → {route.destination}" if route else "Unassigned"
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
            
            # Format: "February 17, 2026" for date, "Tuesday" for day, "03:45 PM" for time
            entry_local = timezone.localtime(log.created_at)
            entry_date = entry_local.strftime("%B %d, %Y")  # February 17, 2026
            entry_day = entry_local.strftime("%A")  # Tuesday
            entry_time = entry_local.strftime("%I:%M %p")  # 03:45 PM
            entry_display = f"{entry_date} ({entry_day}) {entry_time}"
            entry_numeric = entry_display  # Same format for both
            
            departure_time = log.created_at + timedelta(minutes=departure_duration)
            departure_local = timezone.localtime(departure_time)
            departure_date = departure_local.strftime("%B %d, %Y")
            departure_day = departure_local.strftime("%A")
            departure_time_str = departure_local.strftime("%I:%M %p")
            departure_display = f"{departure_date} ({departure_day}) {departure_time_str}"
            
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
