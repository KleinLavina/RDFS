"""
Queue Service Layer
====================
Centralized business logic for queue state transitions.
Ensures consistent behavior regardless of trigger source (QR scan, time-based, manual).
"""

from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from terminal.constants import QUEUE_GROUP_NAME
from terminal.models import EntryLog, SystemSettings, Transaction, TerminalActivity
from vehicles.models import QueueHistory, Vehicle, Wallet


# =============================================================================
# QUEUE STATE CONSTANTS
# =============================================================================
QUEUE_STATUS_QUEUED = "Queued"
QUEUE_STATUS_BOARDING = "Boarding"
QUEUE_STATUS_DEPARTED = "Departed"

DEPARTED_VISIBLE_SECONDS = 60  # How long departed vehicles stay visible


# =============================================================================
# QUEUE STATE SERVICE
# =============================================================================
class QueueService:
    """
    Service layer for all queue-related operations.
    Handles state transitions, countdown logic, and broadcasts.
    """

    @staticmethod
    def get_settings():
        """Get system settings singleton."""
        return SystemSettings.get_solo()

    @staticmethod
    def get_countdown_duration():
        """Get configurable countdown duration in seconds."""
        settings = QueueService.get_settings()
        return getattr(settings, 'countdown_duration_seconds', 30)

    @staticmethod
    def get_refresh_interval():
        """Get configurable refresh interval in seconds."""
        settings = QueueService.get_settings()
        return getattr(settings, 'queue_refresh_interval_seconds', 15)

    @staticmethod
    def get_departure_duration():
        """Get departure duration in minutes."""
        settings = QueueService.get_settings()
        return int(getattr(settings, 'departure_duration_minutes', 30))

    # -------------------------------------------------------------------------
    # STATE TRANSITIONS
    # -------------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def process_entry(vehicle, staff_user=None):
        """
        Process vehicle entry into the queue.
        Returns (success, message, entry_log).
        """
        settings = QueueService.get_settings()
        entry_fee = settings.terminal_fee
        min_deposit = settings.min_deposit_amount
        cooldown_minutes = settings.entry_cooldown_minutes
        departure_duration = settings.departure_duration_minutes

        now = timezone.now()

        # Check if already in queue
        active_log = EntryLog.objects.filter(vehicle=vehicle, is_active=True).first()
        if active_log:
            return False, "Vehicle is already in the queue", active_log

        # Get or create wallet
        wallet, _ = Wallet.objects.get_or_create(vehicle=vehicle)

        # Check cooldown
        recent_entry = (
            EntryLog.objects
            .filter(vehicle=vehicle, status=EntryLog.STATUS_SUCCESS)
            .order_by("-created_at")
            .first()
        )
        if recent_entry and (now - recent_entry.created_at) < timedelta(minutes=cooldown_minutes):
            return False, "Please wait before re-entry (cooldown active)", None

        # Check minimum deposit
        if wallet.balance < min_deposit:
            return False, f"Minimum ₱{min_deposit} deposit required", None

        # Check sufficient balance
        if wallet.balance < entry_fee:
            EntryLog.objects.create(
                vehicle=vehicle,
                staff=staff_user,
                fee_charged=entry_fee,
                wallet_balance_snapshot=wallet.balance,
                status=EntryLog.STATUS_INSUFFICIENT,
                message=f"Insufficient balance for '{vehicle.license_plate}'."
            )
            return False, "Insufficient balance", None

        # Deduct fee and create entry
        wallet.balance -= entry_fee
        wallet.save()

        entry_log = EntryLog.objects.create(
            vehicle=vehicle,
            staff=staff_user,
            fee_charged=entry_fee,
            wallet_balance_snapshot=wallet.balance,
            status=EntryLog.STATUS_SUCCESS,
            message=f"Vehicle '{vehicle.license_plate}' entered terminal."
        )

        # Create queue history record
        departure_snapshot = now + timedelta(minutes=departure_duration)
        QueueHistory.objects.create(
            vehicle=vehicle,
            driver=getattr(vehicle, "assigned_driver", None),
            action="enter",
            departure_time_snapshot=departure_snapshot,
            wallet_balance_snapshot=wallet.balance,
            fee_charged=entry_fee,
        )

        # Broadcast update
        QueueService.broadcast_queue_update()

        return True, f"{vehicle.license_plate} entered terminal", entry_log

    @staticmethod
    @transaction.atomic
    def process_exit(vehicle, staff_user=None):
        """
        Process vehicle exit from the queue.
        Returns (success, message, entry_log).
        """
        now = timezone.now()

        active_log = EntryLog.objects.filter(vehicle=vehicle, is_active=True).first()
        if not active_log:
            return False, "Vehicle is not in the queue", None

        # Mark as departed
        active_log.is_active = False
        active_log.departed_at = now
        active_log.save(update_fields=["is_active", "departed_at"])

        # Create queue history exit record
        wallet = getattr(vehicle, 'wallet', None)
        QueueHistory.objects.create(
            vehicle=vehicle,
            driver=getattr(vehicle, "assigned_driver", None),
            action="exit",
            departure_time_snapshot=now,
            wallet_balance_snapshot=getattr(wallet, 'balance', None) if wallet else None,
            fee_charged=None,
        )

        # Create immutable transaction record
        Transaction.create_from_entry_log(active_log, exit_timestamp=now)

        # Broadcast update
        QueueService.broadcast_queue_update()

        return True, f"{vehicle.license_plate} departed", active_log

    @staticmethod
    @transaction.atomic
    def auto_depart_expired():
        """
        Automatically mark vehicles as departed if their time has expired.
        Called by housekeeping tasks.
        """
        settings = QueueService.get_settings()
        departure_duration = int(getattr(settings, 'departure_duration_minutes', 30))
        now = timezone.now()
        cutoff = now - timedelta(minutes=departure_duration)

        expired_logs = EntryLog.objects.filter(
            is_active=True,
            status=EntryLog.STATUS_SUCCESS,
            created_at__lte=cutoff
        )

        departed_count = 0
        for log in expired_logs:
            log.is_active = False
            log.departed_at = now
            log.save(update_fields=["is_active", "departed_at"])

            # Create transaction record
            Transaction.create_from_entry_log(log, exit_timestamp=now)

            # Create queue history
            vehicle = log.vehicle
            if vehicle:
                wallet = getattr(vehicle, 'wallet', None)
                QueueHistory.objects.create(
                    vehicle=vehicle,
                    driver=getattr(vehicle, "assigned_driver", None),
                    action="exit",
                    departure_time_snapshot=now,
                    wallet_balance_snapshot=getattr(wallet, 'balance', None) if wallet else None,
                    fee_charged=None,
                )

            departed_count += 1

        if departed_count > 0:
            QueueService.broadcast_queue_update()

        return departed_count

    # -------------------------------------------------------------------------
    # QUEUE STATE RETRIEVAL
    # -------------------------------------------------------------------------
    @staticmethod
    def get_queue_state(route_filter=None, include_queued=True):
        """
        Get current queue state for display.
        Returns structured data suitable for JSON serialization.
        """
        now = timezone.now()

        # Run housekeeping first
        QueueService.auto_depart_expired()

        settings = QueueService.get_settings()
        departure_duration = int(getattr(settings, 'departure_duration_minutes', 30))
        countdown_seconds = QueueService.get_countdown_duration()
        refresh_interval = QueueService.get_refresh_interval()
        departed_cutoff = now - timedelta(seconds=DEPARTED_VISIBLE_SECONDS)

        # Fetch active and recently departed logs
        logs = (
            EntryLog.objects
            .select_related("vehicle", "vehicle__assigned_driver", "vehicle__route")
            .filter(status=EntryLog.STATUS_SUCCESS)
            .filter(Q(is_active=True) | Q(departed_at__gte=departed_cutoff))
            .order_by("vehicle__route__origin", "vehicle__route__destination", "created_at")
        )

        if route_filter:
            logs = logs.filter(vehicle__route_id=route_filter)

        # Group by route
        route_groups = OrderedDict()
        for log in logs:
            vehicle = getattr(log, "vehicle", None)
            route = getattr(vehicle, "route", None) if vehicle else None
            route_key = route.id if route else None
            route_name = f"{route.origin} → {route.destination}" if route else "Unassigned"

            if route_key not in route_groups:
                route_groups[route_key] = {
                    "route_name": route_name,
                    "route_id": route_key,
                    "logs": [],
                }
            route_groups[route_key]["logs"].append(log)

        # Build entries for each route
        all_entries = []
        route_sections = []

        for route_key, group in route_groups.items():
            route_name = group["route_name"]
            route_logs = group["logs"]

            # Separate active and departed
            active_logs = [log for log in route_logs if log.is_active]
            departed_logs = [
                log for log in route_logs
                if log.departed_at and log.departed_at >= departed_cutoff
            ]

            # Sort by entry time
            active_logs.sort(key=lambda x: x.created_at)
            departed_logs.sort(key=lambda x: x.departed_at, reverse=True)

            # First active vehicle is boarding
            boarding_log = active_logs[0] if active_logs else None

            route_entries = []
            status_counts = {"Queued": 0, "Boarding": 0, "Departed": 0}

            # Process active vehicles
            for log in active_logs:
                is_boarding = (log == boarding_log)
                status = QUEUE_STATUS_BOARDING if is_boarding else QUEUE_STATUS_QUEUED
                status_counts[status] += 1

                # Skip queued if not requested
                if status == QUEUE_STATUS_QUEUED and not include_queued:
                    continue

                entry = QueueService._format_entry(
                    log, status, departure_duration, countdown_seconds, route_name, now
                )
                route_entries.append(entry)
                all_entries.append(entry)

            # Process departed vehicles
            for log in departed_logs:
                status_counts[QUEUE_STATUS_DEPARTED] += 1
                entry = QueueService._format_entry(
                    log, QUEUE_STATUS_DEPARTED, departure_duration, countdown_seconds, route_name, now
                )
                route_entries.append(entry)
                all_entries.append(entry)

            route_sections.append({
                "name": route_name,
                "route_id": route_key,
                "entries": route_entries,
                "status_summary": status_counts,
                "queued_count": status_counts["Queued"],
            })

        # Count totals
        counts = {
            "queued": sum(1 for e in all_entries if e["status"] == QUEUE_STATUS_QUEUED),
            "boarding": sum(1 for e in all_entries if e["status"] == QUEUE_STATUS_BOARDING),
            "departed": sum(1 for e in all_entries if e["status"] == QUEUE_STATUS_DEPARTED),
        }

        return {
            "entries": all_entries,
            "route_sections": route_sections,
            "counts": counts,
            "server_time": int(now.timestamp()),
            "countdown_duration": countdown_seconds,
            "refresh_interval": refresh_interval,
            "departure_duration_minutes": departure_duration,
        }

    @staticmethod
    def _format_entry(log, status, departure_duration, countdown_seconds, route_name, now):
        """Format a single queue entry for display."""
        vehicle = getattr(log, "vehicle", None)
        driver = getattr(vehicle, "assigned_driver", None) if vehicle else None

        # Calculate expiry timestamps
        expiry_timestamp = None
        departed_countdown_expiry = None

        if status == QUEUE_STATUS_BOARDING:
            boarding_start = log.boarding_started_at or now
            if not log.boarding_started_at:
                EntryLog.objects.filter(pk=log.pk).update(boarding_started_at=boarding_start)
            expiry = boarding_start + timedelta(minutes=departure_duration)
            expiry_timestamp = int(expiry.timestamp())

        elif status == QUEUE_STATUS_DEPARTED and log.departed_at:
            departed_expiry = log.departed_at + timedelta(seconds=countdown_seconds)
            if departed_expiry > now:
                departed_countdown_expiry = int(departed_expiry.timestamp())

        entry_time = timezone.localtime(log.created_at)
        departure_time = log.created_at + timedelta(minutes=departure_duration)
        
        # Format: "February 17, 2026 (Tuesday) 03:45 PM"
        entry_date = entry_time.strftime("%B %d, %Y")
        entry_day = entry_time.strftime("%A")
        entry_time_str = entry_time.strftime("%I:%M %p")
        entry_display = f"{entry_date} ({entry_day}) {entry_time_str}"
        
        departure_local = timezone.localtime(departure_time)
        departure_date = departure_local.strftime("%B %d, %Y")
        departure_day = departure_local.strftime("%A")
        departure_time_str = departure_local.strftime("%I:%M %p")
        departure_display = f"{departure_date} ({departure_day}) {departure_time_str}"

        return {
            "id": log.id,
            "vehicle_plate": vehicle.license_plate if vehicle else "—",
            "vehicle_name": vehicle.vehicle_name if vehicle else "—",
            "vehicle_type": vehicle.vehicle_type if vehicle else "jeepney",
            "driver_name": f"{driver.first_name} {driver.last_name}" if driver else "N/A",
            "route": route_name,
            "route_id": getattr(getattr(vehicle, "route", None), "id", None) if vehicle else None,
            "status": status,
            "entry_time_display": entry_display,
            "entry_time_numeric": entry_display,
            "departure_time_display": departure_display,
            "countdown_active": status == QUEUE_STATUS_BOARDING,
            "expiry_timestamp": expiry_timestamp,
            "departed_countdown_active": status == QUEUE_STATUS_DEPARTED and departed_countdown_expiry is not None,
            "departed_countdown_expiry": departed_countdown_expiry,
        }

    # -------------------------------------------------------------------------
    # TV DISPLAY STATE (excludes queued from main list)
    # -------------------------------------------------------------------------
    @staticmethod
    def get_tv_display_state(route_filter=None):
        """
        Get queue state optimized for TV display.
        Shows all active vehicles (Queued and Boarding) with countdown timers.
        """
        full_state = QueueService.get_queue_state(route_filter=route_filter, include_queued=True)

        # Don't filter - show all active vehicles (Queued and Boarding)
        # Departed vehicles are excluded by default in get_queue_state after visibility timeout
        for section in full_state["route_sections"]:
            section["visible_entries"] = [
                e for e in section["entries"]
                if e["status"] in (QUEUE_STATUS_QUEUED, QUEUE_STATUS_BOARDING)
            ]

        # Collect history events
        history = QueueService._get_recent_history(route_filter)
        full_state["history"] = history

        return full_state

    @staticmethod
    def _get_recent_history(route_filter=None, limit_per_route=3):
        """Get recent queue history events."""
        from vehicles.models import QueueHistory

        queryset = (
            QueueHistory.objects
            .select_related("vehicle__route")
            .order_by("-timestamp")
        )

        if route_filter:
            queryset = queryset.filter(vehicle__route_id=route_filter)

        history_by_route = OrderedDict()
        for event in queryset[:50]:
            vehicle = event.vehicle
            route = getattr(vehicle, "route", None) if vehicle else None
            route_name = f"{route.origin} → {route.destination}" if route else "Unassigned"

            entries = history_by_route.setdefault(route_name, [])
            if len(entries) >= limit_per_route:
                continue

            entries.append({
                "vehicle_plate": getattr(vehicle, "license_plate", "—") if vehicle else "—",
                "action": event.get_action_display(),
                "timestamp": timezone.localtime(event.timestamp).strftime("%I:%M %p"),
            })

        return history_by_route

    # -------------------------------------------------------------------------
    # WEBSOCKET BROADCASTING
    # -------------------------------------------------------------------------
    @staticmethod
    def broadcast_queue_update(route_filter=None):
        """Broadcast queue update to all connected WebSocket clients."""
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        payload = QueueService.get_queue_state(route_filter=route_filter)

        async_to_sync(channel_layer.group_send)(
            QUEUE_GROUP_NAME,
            {
                "type": "queue.update",
                "payload": payload,
            },
        )

    @staticmethod
    def broadcast_tv_update(route_filter=None):
        """Broadcast TV display update to all connected WebSocket clients."""
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        payload = QueueService.get_tv_display_state(route_filter=route_filter)

        async_to_sync(channel_layer.group_send)(
            "tv_display",
            {
                "type": "tv.update",
                "payload": payload,
            },
        )


# =============================================================================
# TRANSACTION SERVICE
# =============================================================================
class TransactionService:
    """Service layer for transaction-related operations."""

    @staticmethod
    def get_daily_transactions(date=None):
        """Get transactions for a specific date."""
        if date is None:
            date = timezone.localtime(timezone.now()).date()

        return Transaction.objects.filter(transaction_date=date).order_by('-entry_timestamp')

    @staticmethod
    def get_daily_revenue(date=None):
        """Get total revenue for a specific date."""
        from django.db.models import Sum

        if date is None:
            date = timezone.localtime(timezone.now()).date()

        result = (
            Transaction.objects
            .filter(transaction_date=date, is_revenue_counted=True)
            .aggregate(total=Sum('fee_charged'))
        )
        return result['total'] or Decimal('0.00')

    @staticmethod
    def get_transactions_in_range(start_date, end_date):
        """Get transactions within a date range."""
        return (
            Transaction.objects
            .filter(transaction_date__gte=start_date, transaction_date__lte=end_date)
            .order_by('-entry_timestamp')
        )

    @staticmethod
    def export_transactions_csv(queryset):
        """Generate CSV content for transactions."""
        import csv
        from io import StringIO

        output = StringIO()
        output.write('\ufeff')  # UTF-8 BOM for Excel compatibility

        writer = csv.writer(output)
        writer.writerow([
            'Date',
            'Year',
            'Month',
            'Day',
            'Vehicle Plate',
            'Driver Name',
            'Route',
            'Entry Time',
            'Exit Time',
            'Fee Charged',
            'Wallet Balance',
        ])

        for tx in queryset:
            entry_time = timezone.localtime(tx.entry_timestamp).strftime("%Y-%m-%d %H:%M:%S")
            exit_time = (
                timezone.localtime(tx.exit_timestamp).strftime("%Y-%m-%d %H:%M:%S")
                if tx.exit_timestamp else "—"
            )

            writer.writerow([
                tx.transaction_date.strftime("%Y-%m-%d"),
                tx.transaction_year,
                tx.transaction_month,
                tx.transaction_day,
                tx.vehicle_plate,
                tx.driver_name,
                tx.route_name,
                entry_time,
                exit_time,
                f"₱{tx.fee_charged:.2f}",
                f"₱{tx.wallet_balance_snapshot:.2f}" if tx.wallet_balance_snapshot else "—",
            ])

        return output.getvalue()
