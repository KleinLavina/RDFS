from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_home, name='reports_home'),  # 👈 Add this line if missing
    path('deposit-analytics/', views.deposit_analytics, name='deposit_analytics'),
    path('deposits-vs-entry-fees/', views.deposits_vs_entry_fees, name='deposits_vs_entry_fees'),
    path('profit-report/', views.profit_report_view, name='profit_report'),
    
    # Backward compatibility redirect for old URL
    path('deposit-vs-revenue/', RedirectView.as_view(pattern_name='reports:deposits_vs_entry_fees', permanent=True)),
]
