from django.urls import path
from . import views
from django.shortcuts import redirect
from django.http import HttpResponseNotFound

app_name = "accounts"

# 🔒 If someone tries to access /login/, redirect them to passenger view instead
def redirect_to_passenger(request):
    return redirect('passenger:public_queue')  # You can change this to fake_404 below if you prefer

# Optional fake 404 version (commented out, can be used instead of redirect)
# def redirect_to_passenger(request):
#     return HttpResponseNotFound("<h1>404 - Page not found</h1>")

urlpatterns = [
    # ✅ Hidden login route (only terminal workers know this)
    path("terminal-access/", views.login_view, name="login"),

    # 🚫 Hide normal /login/ route (redirect to passenger or show 404)
    path("login/", redirect_to_passenger, name="redirect_login"),

    # ✅ Logout (still functional for staff/admin)
    path("logout/", views.logout_view, name="logout"),

    # ✅ Dashboards
    path("dashboard/admin/", views.admin_dashboard_view, name="admin_dashboard"),
    path("dashboard/staff/", views.staff_dashboard_view, name="staff_dashboard"),
    path("dashboard/treasurer/", views.treasurer_dashboard_view, name="treasurer_dashboard"),
    path("admin_dashboard_data/", views.admin_dashboard_data, name="admin_dashboard_data"),


    # ✅ User Management (Admin Only)
    path("manage-users/", views.manage_users, name="manage_users"),
    path("manage-users/create/", views.create_user, name="create_user"),
    path("manage-users/edit/<int:user_id>/", views.edit_user, name="edit_user"),
    path("manage-users/delete/<int:user_id>/", views.delete_user, name="delete_user"),
]
