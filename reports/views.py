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
    """Display overview links to all reports with month-based summary stats."""
    from terminal.models import Transaction
    
    now = timezone.localtime()
    today = now.date()
    current_year = now.year
    current_month = now.month

    # Current month deposits
    month_deposits = (
        Deposit.objects.filter(
            created_at__year=current_year,
            created_at__month=current_month
        ).aggregate(total=Sum("amount"), count=Count("id"))
    )
    
    # Current month terminal fees (from Transaction model)
    month_revenue = (
        Transaction.objects.filter(
            transaction_year=current_year,
            transaction_month=current_month,
            is_revenue_counted=True
        ).aggregate(total=Sum("fee_charged"))["total"] or 0
    )
    
    # Current month transaction count
    month_transactions = (
        Transaction.objects.filter(
            transaction_year=current_year,
            transaction_month=current_month,
            is_revenue_counted=True
        ).count()
    )
    
    # Today's stats
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

    context = {
        "month_deposits": month_deposits["total"] or 0,
        "month_deposit_count": month_deposits["count"] or 0,
        "month_revenue": month_revenue,
        "month_transactions": month_transactions,
        "today_deposits": today_deposits["total"] or 0,
        "today_deposit_count": today_deposits["count"] or 0,
        "today_revenue": today_revenue,
        "current_month_name": now.strftime("%B %Y"),
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
    - Daily totals within selected month
    - Top vehicles by deposit
    - Average deposit amount
    - Peak deposit insights
    """
    import calendar
    from datetime import datetime
    
    now = timezone.localtime()
    today = now.date()
    
    # Get selected month from request or default to current month
    selected_month_str = request.GET.get("month", "")
    
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
    month_start = datetime(selected_year, selected_month, 1).date()
    last_day = calendar.monthrange(selected_year, selected_month)[1]
    month_end = datetime(selected_year, selected_month, last_day).date()
    
    # Get month name for display
    selected_month_name = datetime(selected_year, selected_month, 1).strftime("%B %Y")
    
    # Calculate previous/next month
    if selected_month == 1:
        prev_month_date = datetime(selected_year - 1, 12, 1)
    else:
        prev_month_date = datetime(selected_year, selected_month - 1, 1)
    
    if selected_month == 12:
        next_month_date = datetime(selected_year + 1, 1, 1)
    else:
        next_month_date = datetime(selected_year, selected_month + 1, 1)
    
    # Check if prev/next months have data
    has_prev_month = Deposit.objects.filter(
        created_at__year=prev_month_date.year,
        created_at__month=prev_month_date.month
    ).exists()
    
    # Only allow next month if it's not in the future OR has data
    has_next_month = Deposit.objects.filter(
        created_at__year=next_month_date.year,
        created_at__month=next_month_date.month
    ).exists() and next_month_date.date() <= today

    # Daily totals for the selected month
    daily_data = (
        Deposit.objects
        .filter(
            created_at__year=selected_year,
            created_at__month=selected_month
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total=Sum("amount"),
            count=Count("id")
        )
        .order_by("day")
    )

    # Build complete date range for the month (fill in zeros for missing days)
    labels = []
    daily_totals = []
    daily_counts = []
    daily_map = {item["day"]: item for item in daily_data}
    
    # Track today's index for vertical line
    today_index = -1
    is_current_month = (selected_year == today.year and selected_month == today.month)
    
    for day_num in range(1, last_day + 1):
        day = datetime(selected_year, selected_month, day_num).date()
        labels.append(day.strftime("%b %d"))
        
        # Check if this is today
        if is_current_month and day == today:
            today_index = day_num - 1
        
        if day in daily_map:
            daily_totals.append(float(daily_map[day]["total"] or 0))
            daily_counts.append(daily_map[day]["count"] or 0)
        else:
            daily_totals.append(0)
            daily_counts.append(0)

    total_deposits = sum(daily_totals)
    total_count = sum(daily_counts)
    avg_deposit = total_deposits / total_count if total_count > 0 else 0
    
    # Peak deposit day (highest amount)
    peak_day_index = daily_totals.index(max(daily_totals)) if daily_totals and max(daily_totals) > 0 else -1
    peak_day_date = None
    peak_day_amount = 0
    if peak_day_index >= 0:
        peak_day_date = datetime(selected_year, selected_month, peak_day_index + 1).date()
        peak_day_amount = daily_totals[peak_day_index]
    
    # Highest transaction volume day
    busiest_day_index = daily_counts.index(max(daily_counts)) if daily_counts and max(daily_counts) > 0 else -1
    busiest_day_date = None
    busiest_day_count = 0
    if busiest_day_index >= 0:
        busiest_day_date = datetime(selected_year, selected_month, busiest_day_index + 1).date()
        busiest_day_count = daily_counts[busiest_day_index]

    # Top 5 vehicles by total deposit (for selected month)
    top_vehicles = (
        Deposit.objects
        .filter(
            created_at__year=selected_year,
            created_at__month=selected_month
        )
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

    # Recent deposits (within selected month)
    recent_deposits = (
        Deposit.objects
        .filter(
            created_at__year=selected_year,
            created_at__month=selected_month
        )
        .select_related("wallet__vehicle__assigned_driver")
        .order_by("-created_at")[:10]
    )
    
    # Get all months with deposits for navigation
    available_months = (
        Deposit.objects
        .annotate(month=TruncDate("created_at", kind="month"))
        .values("month")
        .distinct()
        .order_by("-month")
    )

    context = {
        "labels": labels,
        "daily_totals": daily_totals,
        "daily_counts": daily_counts,
        "total_deposits": total_deposits,
        "total_count": total_count,
        "avg_deposit": avg_deposit,
        "peak_day_date": peak_day_date,
        "peak_day_amount": peak_day_amount,
        "busiest_day_date": busiest_day_date,
        "busiest_day_count": busiest_day_count,
        "top_vehicles": top_vehicles,
        "recent_deposits": recent_deposits,
        "selected_month": f"{selected_year}-{selected_month:02d}",
        "selected_month_name": selected_month_name,
        "prev_month": f"{prev_month_date.year}-{prev_month_date.month:02d}",
        "next_month": f"{next_month_date.year}-{next_month_date.month:02d}",
        "has_prev_month": has_prev_month,
        "has_next_month": has_next_month,
        "available_months": available_months,
        "today_index": today_index,
        "is_current_month": is_current_month,
    }
    return render(request, "reports/deposit_analytics.html", context)


# ============================================================
# 💵 DEPOSIT VS REVENUE
# ============================================================
@login_required(login_url='login')
@user_passes_test(is_admin)
def deposit_vs_revenue(request):
    """
    Compare deposits vs terminal fees with month-based filtering.
    Combines analytics from deposit-analytics and profit-report.
    Uses Transaction model for accurate terminal fee data.
    """
    import calendar
    import csv
    from django.http import HttpResponse
    from terminal.models import Transaction
    
    now = timezone.localtime()
    today = now.date()
    
    # Handle CSV export
    if request.GET.get('export') == 'csv':
        selected_month_str = request.GET.get("month", "")
        
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
        
        # Get deposits for the month
        deposits = Deposit.objects.filter(
            created_at__year=selected_year,
            created_at__month=selected_month
        ).annotate(day=TruncDate("created_at")).values("day").annotate(
            total=Sum("amount")
        ).order_by("day")
        
        # Get terminal fees for the month
        transactions = Transaction.objects.filter(
            transaction_year=selected_year,
            transaction_month=selected_month,
            is_revenue_counted=True
        ).values('transaction_day').annotate(
            total=Sum('fee_charged')
        ).order_by('transaction_day')
        
        # Build data map
        deposit_map = {item["day"]: float(item["total"] or 0) for item in deposits}
        revenue_map = {item['transaction_day']: float(item['total'] or 0) for item in transactions}
        
        # Generate filename
        filename = f"deposit_vs_revenue_{selected_year}-{selected_month:02d}.csv"
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Day', 'Deposits (₱)', 'Terminal Fees (₱)', 'Net Balance (₱)'])
        
        last_day = calendar.monthrange(selected_year, selected_month)[1]
        for day_num in range(1, last_day + 1):
            day_date = datetime(selected_year, selected_month, day_num).date()
            deposit_amount = deposit_map.get(day_date, 0)
            revenue_amount = revenue_map.get(day_num, 0)
            net = deposit_amount - revenue_amount
            
            writer.writerow([
                day_date.strftime('%Y-%m-%d'),
                day_num,
                f"{deposit_amount:.2f}",
                f"{revenue_amount:.2f}",
                f"{net:.2f}"
            ])
        
        return response
    
    # Get selected month from request or default to current month
    selected_month_str = request.GET.get("month", "")
    
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
    month_start = datetime(selected_year, selected_month, 1).date()
    last_day = calendar.monthrange(selected_year, selected_month)[1]
    month_end = datetime(selected_year, selected_month, last_day).date()
    
    # Get month name for display
    selected_month_name = datetime(selected_year, selected_month, 1).strftime("%B %Y")
    
    # Calculate previous/next month
    if selected_month == 1:
        prev_month_date = datetime(selected_year - 1, 12, 1)
    else:
        prev_month_date = datetime(selected_year, selected_month - 1, 1)
    
    if selected_month == 12:
        next_month_date = datetime(selected_year + 1, 1, 1)
    else:
        next_month_date = datetime(selected_year, selected_month + 1, 1)
    
    # Check if prev/next months have data (check both deposits and transactions)
    has_prev_month = (
        Deposit.objects.filter(
            created_at__year=prev_month_date.year,
            created_at__month=prev_month_date.month
        ).exists() or
        Transaction.objects.filter(
            transaction_year=prev_month_date.year,
            transaction_month=prev_month_date.month,
            is_revenue_counted=True
        ).exists()
    )
    
    has_next_month = (
        (Deposit.objects.filter(
            created_at__year=next_month_date.year,
            created_at__month=next_month_date.month
        ).exists() or
        Transaction.objects.filter(
            transaction_year=next_month_date.year,
            transaction_month=next_month_date.month,
            is_revenue_counted=True
        ).exists()) and next_month_date.date() <= today
    )
    
    # Aggregate deposits by day for selected month
    deposit_data = (
        Deposit.objects
        .filter(
            created_at__year=selected_year,
            created_at__month=selected_month
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("amount"))
        .order_by("day")
    )
    deposit_map = {item["day"]: float(item["total"] or 0) for item in deposit_data}
    
    # Aggregate terminal fees by day for selected month (using Transaction model)
    revenue_data = (
        Transaction.objects
        .filter(
            transaction_year=selected_year,
            transaction_month=selected_month,
            is_revenue_counted=True
        )
        .values('transaction_day')
        .annotate(total=Sum('fee_charged'))
        .order_by('transaction_day')
    )
    revenue_map = {item['transaction_day']: float(item['total'] or 0) for item in revenue_data}
    
    # Build complete date range for the month
    chart_labels = []
    deposits_data = []
    revenue_values = []
    
    # Track today's index for vertical line
    today_index = -1
    is_current_month = (selected_year == today.year and selected_month == today.month)
    
    for day_num in range(1, last_day + 1):
        day = datetime(selected_year, selected_month, day_num).date()
        chart_labels.append(day.strftime("%b %d"))
        
        # Check if this is today
        if is_current_month and day == today:
            today_index = day_num - 1
        
        deposits_data.append(deposit_map.get(day, 0))
        revenue_values.append(revenue_map.get(day_num, 0))
    
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
    
    # Peak days
    peak_deposit_index = deposits_data.index(max(deposits_data)) if deposits_data and max(deposits_data) > 0 else -1
    peak_deposit_day = None
    peak_deposit_amount = 0
    if peak_deposit_index >= 0:
        peak_deposit_day = datetime(selected_year, selected_month, peak_deposit_index + 1).date()
        peak_deposit_amount = deposits_data[peak_deposit_index]
    
    peak_revenue_index = revenue_values.index(max(revenue_values)) if revenue_values and max(revenue_values) > 0 else -1
    peak_revenue_day = None
    peak_revenue_amount = 0
    if peak_revenue_index >= 0:
        peak_revenue_day = datetime(selected_year, selected_month, peak_revenue_index + 1).date()
        peak_revenue_amount = revenue_values[peak_revenue_index]
    
    # Get all months with data for navigation
    deposit_months = set(
        Deposit.objects
        .values_list('created_at__year', 'created_at__month')
        .distinct()
    )
    transaction_months = set(
        Transaction.objects
        .filter(is_revenue_counted=True)
        .values_list('transaction_year', 'transaction_month')
        .distinct()
    )
    all_months = sorted(deposit_months | transaction_months, reverse=True)
    
    available_months = []
    for year, month in all_months:
        month_date = datetime(year, month, 1)
        available_months.append({
            'transaction_year': year,
            'transaction_month': month,
            'month_name': month_date.strftime("%B %Y")
        })

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
        "peak_deposit_day": peak_deposit_day,
        "peak_deposit_amount": peak_deposit_amount,
        "peak_revenue_day": peak_revenue_day,
        "peak_revenue_amount": peak_revenue_amount,
        "selected_month": f"{selected_year}-{selected_month:02d}",
        "selected_month_name": selected_month_name,
        "selected_year": selected_year,
        "selected_month_num": selected_month,
        "prev_month": f"{prev_month_date.year}-{prev_month_date.month:02d}",
        "next_month": f"{next_month_date.year}-{next_month_date.month:02d}",
        "has_prev_month": has_prev_month,
        "has_next_month": has_next_month,
        "available_months": available_months,
        "today_index": today_index,
        "is_current_month": is_current_month,
    }
    return render(request, "reports/deposit_vs_revenue.html", context)


# ============================================================
# 📈 TERMINAL FEE ANALYTICS (Profit Report)
# ============================================================
@login_required(login_url='login')
@user_passes_test(is_admin)
def profit_report_view(request):
    """
    Terminal Fee Analytics with month-based filtering.
    Uses Transaction model for archived data with indexed fields.
    Mirrors deposit analytics functionality.
    """
    import calendar
    import csv
    from django.http import HttpResponse
    from terminal.models import Transaction
    
    now = timezone.localtime()
    today = now.date()
    
    # Handle CSV export
    if request.GET.get('export') == 'csv':
        selected_month_str = request.GET.get("month", "")
        
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
        
        # Build query
        transactions = Transaction.objects.filter(
            transaction_year=selected_year,
            transaction_month=selected_month,
            is_revenue_counted=True
        )
        
        # Generate filename
        filename = f"terminal_fee_report_{selected_year}-{selected_month:02d}.csv"
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Transaction Date', 'Entry Time', 'Exit Time',
            'Vehicle Plate', 'Driver Name', 'Route',
            'Terminal Fee', 'Wallet Balance',
            'Year', 'Month', 'Day'
        ])
        
        for tx in transactions:
            writer.writerow([
                tx.transaction_date,
                tx.entry_timestamp.strftime('%H:%M:%S'),
                tx.exit_timestamp.strftime('%H:%M:%S') if tx.exit_timestamp else '—',
                tx.vehicle_plate,
                tx.driver_name,
                tx.route_name,
                f"{tx.fee_charged:.2f}",
                f"{tx.wallet_balance_snapshot:.2f}" if tx.wallet_balance_snapshot else '—',
                tx.transaction_year,
                tx.transaction_month,
                tx.transaction_day
            ])
        
        return response
    
    # Get selected month from request or default to most recent with data
    selected_month_str = request.GET.get("month", "")
    
    if selected_month_str:
        try:
            selected_date = datetime.strptime(selected_month_str, "%Y-%m")
            selected_year = selected_date.year
            selected_month = selected_date.month
        except ValueError:
            # Default to most recent month with data
            latest_tx = Transaction.objects.filter(is_revenue_counted=True).order_by('-transaction_date').first()
            if latest_tx:
                selected_year = latest_tx.transaction_year
                selected_month = latest_tx.transaction_month
            else:
                selected_year = now.year
                selected_month = now.month
    else:
        # Default to most recent month with data
        latest_tx = Transaction.objects.filter(is_revenue_counted=True).order_by('-transaction_date').first()
        if latest_tx:
            selected_year = latest_tx.transaction_year
            selected_month = latest_tx.transaction_month
        else:
            selected_year = now.year
            selected_month = now.month
    
    # Calculate month boundaries
    month_start = datetime(selected_year, selected_month, 1).date()
    last_day = calendar.monthrange(selected_year, selected_month)[1]
    month_end = datetime(selected_year, selected_month, last_day).date()
    
    # Get month name for display
    selected_month_name = datetime(selected_year, selected_month, 1).strftime("%B %Y")
    
    # Calculate previous/next month
    if selected_month == 1:
        prev_month_date = datetime(selected_year - 1, 12, 1)
    else:
        prev_month_date = datetime(selected_year, selected_month - 1, 1)
    
    if selected_month == 12:
        next_month_date = datetime(selected_year + 1, 1, 1)
    else:
        next_month_date = datetime(selected_year, selected_month + 1, 1)
    
    # Check if prev/next months have data
    has_prev_month = Transaction.objects.filter(
        transaction_year=prev_month_date.year,
        transaction_month=prev_month_date.month,
        is_revenue_counted=True
    ).exists()
    
    has_next_month = Transaction.objects.filter(
        transaction_year=next_month_date.year,
        transaction_month=next_month_date.month,
        is_revenue_counted=True
    ).exists() and next_month_date.date() <= today
    
    # Query transactions for selected month
    transactions = Transaction.objects.filter(
        transaction_year=selected_year,
        transaction_month=selected_month,
        is_revenue_counted=True
    )
    
    # Daily breakdown
    daily_data = transactions.values('transaction_day').annotate(
        daily_revenue=Sum('fee_charged'),
        daily_count=Count('id')
    ).order_by('transaction_day')
    
    # Build complete date range for the month
    labels = []
    daily_revenues = []
    daily_counts = []
    daily_map = {item['transaction_day']: item for item in daily_data}
    
    # Track today's index for vertical line
    today_index = -1
    is_current_month = (selected_year == today.year and selected_month == today.month)
    
    for day_num in range(1, last_day + 1):
        day = datetime(selected_year, selected_month, day_num).date()
        labels.append(day.strftime("%b %d"))
        
        # Check if this is today
        if is_current_month and day == today:
            today_index = day_num - 1
        
        if day_num in daily_map:
            daily_revenues.append(float(daily_map[day_num]['daily_revenue'] or 0))
            daily_counts.append(daily_map[day_num]['daily_count'] or 0)
        else:
            daily_revenues.append(0)
            daily_counts.append(0)
    
    # Summary metrics
    total_revenue = sum(daily_revenues)
    total_transactions = sum(daily_counts)
    avg_fee = total_revenue / total_transactions if total_transactions > 0 else 0
    
    # Peak revenue day
    peak_day_index = daily_revenues.index(max(daily_revenues)) if daily_revenues and max(daily_revenues) > 0 else -1
    peak_day_date = None
    peak_day_amount = 0
    if peak_day_index >= 0:
        peak_day_date = datetime(selected_year, selected_month, peak_day_index + 1).date()
        peak_day_amount = daily_revenues[peak_day_index]
    
    # Busiest day (by transaction count)
    busiest_day_index = daily_counts.index(max(daily_counts)) if daily_counts and max(daily_counts) > 0 else -1
    busiest_day_date = None
    busiest_day_count = 0
    if busiest_day_index >= 0:
        busiest_day_date = datetime(selected_year, selected_month, busiest_day_index + 1).date()
        busiest_day_count = daily_counts[busiest_day_index]
    
    # Top 10 vehicles by total fees
    top_vehicles = transactions.values('vehicle_plate', 'driver_name').annotate(
        transaction_count=Count('id'),
        total_fees=Sum('fee_charged'),
        avg_fee=Avg('fee_charged')
    ).order_by('-total_fees')[:10]
    
    # Route performance
    route_performance = transactions.values('route_name').annotate(
        transaction_count=Count('id'),
        total_revenue=Sum('fee_charged'),
        avg_fee=Avg('fee_charged')
    ).order_by('-total_revenue')[:10]
    
    # Get all months with transactions for navigation
    available_months_data = (
        Transaction.objects
        .filter(is_revenue_counted=True)
        .values('transaction_year', 'transaction_month')
        .distinct()
        .order_by('-transaction_year', '-transaction_month')
    )
    
    # Format available months
    available_months = []
    for item in available_months_data:
        month_date = datetime(item['transaction_year'], item['transaction_month'], 1)
        available_months.append({
            'transaction_year': item['transaction_year'],
            'transaction_month': item['transaction_month'],
            'month_name': month_date.strftime("%B %Y")
        })

    context = {
        "labels": labels,
        "daily_revenues": daily_revenues,
        "daily_counts": daily_counts,
        "total_revenue": total_revenue,
        "total_transactions": total_transactions,
        "avg_fee": avg_fee,
        "peak_day_date": peak_day_date,
        "peak_day_amount": peak_day_amount,
        "busiest_day_date": busiest_day_date,
        "busiest_day_count": busiest_day_count,
        "top_vehicles": top_vehicles,
        "route_performance": route_performance,
        "selected_month": f"{selected_year}-{selected_month:02d}",
        "selected_month_name": selected_month_name,
        "selected_year": selected_year,
        "selected_month_num": selected_month,
        "prev_month": f"{prev_month_date.year}-{prev_month_date.month:02d}",
        "next_month": f"{next_month_date.year}-{next_month_date.month:02d}",
        "has_prev_month": has_prev_month,
        "has_next_month": has_next_month,
        "available_months": available_months,
        "today_index": today_index,
        "is_current_month": is_current_month,
    }
    return render(request, "reports/profit_report.html", context)
