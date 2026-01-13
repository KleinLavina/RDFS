# reports/views.py
from django.shortcuts import render
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncDate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from collections import OrderedDict

from accounts.utils import is_admin
from vehicles.models import Deposit, Vehicle
from terminal.models import EntryLog, SystemSettings, TerminalActivity
from .models import Profit


# ============================================================
# 📊 REPORTS HOME
# ============================================================
@login_required(login_url='login')
@user_passes_test(is_admin)
def reports_home(request):
    """Display overview links to all reports with summary stats."""
    now = timezone.localtime()
    today = now.date()
    week_start = today - timedelta(days=7)
    month_start = today - timedelta(days=30)

    # Quick stats for dashboard
    today_deposits = (
        Deposit.objects.filter(created_at__date=today)
        .aggregate(total=Sum("amount"), count=Count("id"))
    )
    
    today_revenue = (
        EntryLog.objects.filter(
            created_at__date=today,
            status=EntryLog.STATUS_SUCCESS
        ).aggregate(total=Sum("fee_charged"))["total"] or 0
    )

    week_deposits = (
        Deposit.objects.filter(created_at__date__gte=week_start)
        .aggregate(total=Sum("amount"))["total"] or 0
    )

    week_revenue = (
        EntryLog.objects.filter(
            created_at__date__gte=week_start,
            status=EntryLog.STATUS_SUCCESS
        ).aggregate(total=Sum("fee_charged"))["total"] or 0
    )

    active_vehicles = Vehicle.objects.filter(status__in=["queued", "boarding"]).count()
    
    # Count entry logs for today
    today_entry_logs = EntryLog.objects.filter(created_at__date=today).count()

    context = {
        "today_deposits": today_deposits["total"] or 0,
        "today_deposit_count": today_deposits["count"] or 0,
        "today_revenue": today_revenue,
        "week_deposits": week_deposits,
        "week_revenue": week_revenue,
        "active_vehicles": active_vehicles,
        "today_entry_logs": today_entry_logs,
    }
    return render(request, 'reports/reports_home.html', context)


# ============================================================
# 💰 DEPOSIT ANALYTICS
# ============================================================
@login_required(login_url='login')
@user_passes_test(is_admin)
def deposit_analytics(request):
    """
    Show deposit trends with accurate data:
    - 7-day daily totals
    - Top vehicles by deposit
    - Average deposit amount
    """
    now = timezone.localtime()
    today = now.date()
    
    # Get date range from request or default to 7 days
    days = int(request.GET.get("days", 7))
    start_date = today - timedelta(days=days - 1)

    # Daily totals for the selected period
    daily_data = (
        Deposit.objects
        .filter(created_at__date__gte=start_date, created_at__date__lte=today)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total=Sum("amount"),
            count=Count("id")
        )
        .order_by("day")
    )

    # Build complete date range (fill in zeros for missing days)
    labels = []
    daily_totals = []
    daily_counts = []
    daily_map = {item["day"]: item for item in daily_data}
    
    for i in range(days):
        day = start_date + timedelta(days=i)
        labels.append(day.strftime("%b %d"))
        if day in daily_map:
            daily_totals.append(float(daily_map[day]["total"] or 0))
            daily_counts.append(daily_map[day]["count"] or 0)
        else:
            daily_totals.append(0)
            daily_counts.append(0)

    total_deposits = sum(daily_totals)
    total_count = sum(daily_counts)
    avg_deposit = total_deposits / total_count if total_count > 0 else 0

    # Top 5 vehicles by total deposit (all time)
    top_vehicles = (
        Deposit.objects
        .values(
            "wallet__vehicle__license_plate",
            "wallet__vehicle__assigned_driver__first_name",
            "wallet__vehicle__assigned_driver__last_name"
        )
        .annotate(
            total=Sum("amount"),
            count=Count("id")
        )
        .order_by("-total")[:5]
    )

    # Recent deposits
    recent_deposits = (
        Deposit.objects
        .select_related("wallet__vehicle__assigned_driver")
        .order_by("-created_at")[:10]
    )

    context = {
        "labels": labels,
        "daily_totals": daily_totals,
        "daily_counts": daily_counts,
        "total_deposits": total_deposits,
        "total_count": total_count,
        "avg_deposit": avg_deposit,
        "top_vehicles": top_vehicles,
        "recent_deposits": recent_deposits,
        "days": days,
        "start_date": start_date,
        "end_date": today,
    }
    return render(request, "reports/deposit_analytics.html", context)


# ============================================================
# 💵 DEPOSIT VS REVENUE
# ============================================================
@login_required(login_url='login')
@user_passes_test(is_admin)
def deposit_vs_revenue(request):
    """
    Compare total deposits vs total terminal fees per day.
    Accurate calculation using proper status filtering.
    """
    now = timezone.localtime()
    today = now.date()
    
    # Get date range
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = today
            start_date = end_date - timedelta(days=6)
    else:
        end_date = today
        start_date = end_date - timedelta(days=6)

    # Ensure end_date is not in the future
    if end_date > today:
        end_date = today

    # Aggregate deposits by day
    deposit_data = (
        Deposit.objects
        .filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("amount"))
        .order_by("day")
    )
    deposit_map = {item["day"]: float(item["total"] or 0) for item in deposit_data}

    # Aggregate revenue by day (only successful entries)
    revenue_data = (
        EntryLog.objects
        .filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status=EntryLog.STATUS_SUCCESS
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("fee_charged"))
        .order_by("day")
    )
    revenue_map = {item["day"]: float(item["total"] or 0) for item in revenue_data}

    # Build complete date range
    chart_labels = []
    deposits_data = []
    revenue_values = []
    
    for i in range((end_date - start_date).days + 1):
        day = start_date + timedelta(days=i)
        chart_labels.append(day.strftime("%b %d"))
        deposits_data.append(deposit_map.get(day, 0))
        revenue_values.append(revenue_map.get(day, 0))

    # Summary totals
    total_deposit = sum(deposits_data)
    total_revenue = sum(revenue_values)
    
    # Calculate ratio (revenue as percentage of deposits)
    if total_deposit > 0:
        ratio = (total_revenue / total_deposit) * 100
        ratio_label = "Revenue ÷ Deposits"
    else:
        ratio = 0
        ratio_label = "No deposits recorded"
    
    # Net balance (deposits - revenue = money still in wallets)
    net_balance = total_deposit - total_revenue

    context = {
        "chart_labels": chart_labels,
        "deposits_data": deposits_data,
        "revenue_data": revenue_values,
        "total_deposit": total_deposit,
        "total_revenue": total_revenue,
        "ratio": ratio,
        "ratio_label": ratio_label,
        "has_deposits": total_deposit > 0,
        "net_balance": net_balance,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "today": today.strftime("%Y-%m-%d"),
        "selected_range": f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}",
    }
    return render(request, "reports/deposit_vs_revenue.html", context)


# ============================================================
# 📈 PROFIT TREND (Profit Report)
# ============================================================
@login_required(login_url='login')
@user_passes_test(is_admin)
def profit_report_view(request):
    """
    Visual profit trend with accurate calculations.
    Profit = Terminal Revenue (fees collected)
    """
    now = timezone.localtime()
    today = now.date()

    # Get date range
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = today - timedelta(days=29)
            end_date = today
    else:
        start_date = today - timedelta(days=29)
        end_date = today

    # Calculate daily revenue (profit = fees collected)
    daily_revenue = (
        EntryLog.objects
        .filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status=EntryLog.STATUS_SUCCESS
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            revenue=Sum("fee_charged"),
            entries=Count("id")
        )
        .order_by("day")
    )
    revenue_map = {item["day"]: item for item in daily_revenue}

    # Build complete date range
    profit_labels = []
    profit_values = []
    entry_counts = []
    
    for i in range((end_date - start_date).days + 1):
        day = start_date + timedelta(days=i)
        profit_labels.append(day.strftime("%b %d"))
        if day in revenue_map:
            profit_values.append(float(revenue_map[day]["revenue"] or 0))
            entry_counts.append(revenue_map[day]["entries"] or 0)
        else:
            profit_values.append(0)
            entry_counts.append(0)

    # Summary metrics
    total_profit = sum(profit_values)
    total_entries = sum(entry_counts)
    avg_daily_profit = total_profit / len(profit_values) if profit_values else 0
    best_day_index = profit_values.index(max(profit_values)) if profit_values else 0
    best_day = profit_labels[best_day_index] if profit_labels else "N/A"
    best_day_amount = max(profit_values) if profit_values else 0

    # Get Profit model records if they exist
    profit_records = Profit.objects.filter(
        date_recorded__date__gte=start_date,
        date_recorded__date__lte=end_date
    ).order_by("-date_recorded")

    # Today's profit
    today_profit = (
        EntryLog.objects
        .filter(created_at__date=today, status=EntryLog.STATUS_SUCCESS)
        .aggregate(total=Sum("fee_charged"))["total"] or 0
    )

    context = {
        "profit_labels": profit_labels,
        "profit_values": profit_values,
        "entry_counts": entry_counts,
        "total": total_profit,
        "total_entries": total_entries,
        "avg_daily_profit": avg_daily_profit,
        "best_day": best_day,
        "best_day_amount": best_day_amount,
        "today_profit": today_profit,
        "profits": profit_records,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }
    return render(request, "reports/profit_report.html", context)
