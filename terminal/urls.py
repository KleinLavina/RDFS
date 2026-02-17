from django.urls import path
from . import views

app_name = 'terminal'

urlpatterns = [
    path('deposit-menu/', views.deposit_menu, name='deposit_menu'),
    path('deposit-history/', views.deposit_history, name='deposit_history'),
    path('deposits/', views.deposits, name='deposits'),
    path('deposit-receipt/<int:deposit_id>/', views.deposit_receipt, name='deposit_receipt'),
    path('transactions/', views.transactions_view, name='transactions'),
    path('past-transactions/', views.past_transactions_view, name='past_transactions'),
    path('queue/', views.terminal_queue, name='terminal_queue'),
    path('queue-data/', views.queue_data, name='queue_data'),
    path('manage-queue/', views.manage_queue, name='manage_queue'),
    path('simple-queue/', views.simple_queue_view, name='simple_queue_view'),
    path('qr-scan-entry/', views.qr_scan_entry, name='qr_scan_entry'),
    path('qr-exit/', views.qr_exit_validation, name='qr_exit_validation'),
    path('qr-exit-page/', views.qr_exit_page, name='qr_exit_page'),
    path('queue-history/', views.queue_history, name='queue_history'),
    path('manage-routes/', views.manage_routes, name='manage_routes'),
    path('system-settings/', views.system_settings, name='system_settings'),
    path('system-and-routes/', views.system_and_routes, name='system_and_routes'),
    path('mark-departed/<int:entry_id>/', views.mark_departed, name='mark_departed'),
    path('update-departure/<int:entry_id>/', views.update_departure_time, name='update_departure_time'),
    path('ajax-add-deposit/', views.ajax_add_deposit, name='ajax_add_deposit'),
    path('ajax-get-wallet-balance/', views.ajax_get_wallet_balance, name='ajax_get_wallet_balance'),

    # --- TV Display Routes ---
    path('tv-display/', views.tv_display_view, name='tv_display'),
    path('tv-display/<slug:route_name>/', views.tv_display_view, name='tv_display_route'),

    # --- API Endpoints for Partial Updates ---
    path('api/queue/', views.public_queue_api, name='public_queue_api'),
    path('api/tv-display/', views.tv_display_api, name='tv_display_api'),
    path('api/settings/', views.queue_settings_api, name='queue_settings_api'),

    path("deposit-analytics/", views.deposit_analytics, name="deposit_analytics"),
    path("deposit-vs-revenue/", views.deposit_vs_revenue, name="deposit_vs_revenue"),
]
