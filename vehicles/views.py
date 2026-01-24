# vehicles/views.py
import base64
import cv2
import numpy as np
import pytesseract
import re
import json
from decimal import Decimal
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.template.loader import render_to_string

from accounts.utils import is_staff_admin_or_admin, is_admin
from .models import Driver, Vehicle, Wallet, Deposit, QueueHistory
from .forms import DriverRegistrationForm, DriverEditForm, VehicleRegistrationForm

# ✅ Path for your installed Tesseract OCR (adjust if needed)
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

DRIVER_EDIT_FIELD_ORDER = [
    'first_name', 'middle_name', 'last_name', 'suffix',
    'birth_date', 'birth_place', 'blood_type',
    'mobile_number', 'email',
    'street', 'barangay', 'zip_code',
    'city_municipality', 'province',
    'license_number', 'license_expiry',
    'emergency_contact_name', 'emergency_contact_number', 'emergency_contact_relationship',
    'driver_photo'
]

DRIVER_EDIT_ICON_MAP = {
    'first_name': 'fa-user',
    'middle_name': 'fa-user-pen',
    'last_name': 'fa-user',
    'suffix': 'fa-id-badge',
    'birth_date': 'fa-cake-candles',
    'birth_place': 'fa-map-marker-alt',
    'blood_type': 'fa-heart',
    'mobile_number': 'fa-phone',
    'email': 'fa-envelope',
    'street': 'fa-road',
    'barangay': 'fa-city',
    'zip_code': 'fa-mail-bulk',
    'city_municipality': 'fa-building',
    'province': 'fa-flag',
    'license_number': 'fa-id-card',
    'license_expiry': 'fa-calendar-check',
    'emergency_contact_name': 'fa-handshake',
    'emergency_contact_number': 'fa-phone-alt',
    'emergency_contact_relationship': 'fa-people-group',
    'driver_photo': 'fa-camera'
}

DRIVER_EDIT_SPANS = {
    'street': 2,
    'driver_photo': 2,
    'license_number': 2,
    'emergency_contact_name': 2,
}

VEHICLE_EDIT_FIELD_ORDER = [
    'vehicle_name', 'vehicle_type', 'ownership_type',
    'assigned_driver', 'route',
    'cr_number', 'or_number', 'vin_number', 'year_model',
    'registration_number', 'registration_expiry', 'license_plate',
    'seat_capacity'
]

VEHICLE_EDIT_ICON_MAP = {
    'vehicle_name': 'fa-car',
    'vehicle_type': 'fa-car-side',
    'ownership_type': 'fa-handshake',
    'assigned_driver': 'fa-user-tie',
    'route': 'fa-route',
    'cr_number': 'fa-file-signature',
    'or_number': 'fa-receipt',
    'vin_number': 'fa-barcode',
    'year_model': 'fa-calendar-alt',
    'registration_number': 'fa-id-badge',
    'registration_expiry': 'fa-calendar-check',
    'license_plate': 'fa-hashtag',
    'seat_capacity': 'fa-users'
}

VEHICLE_EDIT_SPANS = {
    'vehicle_name': 2,
    'assigned_driver': 2,
    'seat_capacity': 1,
}


def format_form_errors(form, form_type="Form"):
    """
    Extracts all form errors and formats them into user-friendly messages.
    Returns a list of error messages with field labels.
    """
    error_list = []
    
    # Non-field errors (general form errors)
    if form.non_field_errors():
        for error in form.non_field_errors():
            error_list.append(str(error))
    
    # Field-specific errors
    for field_name, errors in form.errors.items():
        if field_name == '__all__':
            continue  # Already handled above
        
        # Get the field label for better readability
        if field_name in form.fields:
            field_label = form.fields[field_name].label or field_name.replace('_', ' ').title()
        else:
            field_label = field_name.replace('_', ' ').title()
        
        # Add each error for this field
        for error in errors:
            # If error already has emoji/formatting, use as-is
            if error.startswith('❌') or error.startswith('⚠️'):
                error_list.append(f"{field_label}: {error}")
            else:
                error_list.append(f"❌ {field_label}: {error}")
    
    return error_list


def _is_plate_duplicate_message(text):
    if not text:
        return False
    normalized = str(text).lower()

    contains_plate_key = 'license_plate' in normalized or 'plate' in normalized
    if not contains_plate_key:
        return False

    duplicate_indicators = [
        'already registered',
        'already exists',
        'duplicate',
        'duplicate key',
        'unique constraint failed',
        'plate already exists',
        'already taken',
        'license plate already exists'
    ]
    return any(indicator in normalized for indicator in duplicate_indicators)


def _build_form_field_rows(form, field_order, icon_map, span_map):
    for field_obj in form.fields.values():
        classes = field_obj.widget.attrs.get('class', '')
        extras = " ".join(filter(None, [classes, "rdfs-edit-input"]))
        field_obj.widget.attrs['class'] = extras

    rows = []
    for field_name in field_order:
        if field_name in form.fields:
            rows.append({
                'field': form[field_name],
                'icon': icon_map.get(field_name, 'fa-circle-info'),
                'span': span_map.get(field_name, 1),
            })
    return rows


def _render_driver_edit_partial(request, form, driver):
    context = {
        'form': form,
        'driver': driver,
        'field_rows': _build_form_field_rows(
            form,
            DRIVER_EDIT_FIELD_ORDER,
            DRIVER_EDIT_ICON_MAP,
            DRIVER_EDIT_SPANS
        ),
    }
    return render_to_string('vehicles/includes/driver_edit_form.html', context, request=request)


def _render_vehicle_edit_partial(request, form, vehicle):
    context = {
        'form': form,
        'vehicle': vehicle,
        'field_rows': _build_form_field_rows(
            form,
            VEHICLE_EDIT_FIELD_ORDER,
            VEHICLE_EDIT_ICON_MAP,
            VEHICLE_EDIT_SPANS
        ),
    }
    return render_to_string('vehicles/includes/vehicle_edit_form.html', context, request=request)


def maybe_show_plate_duplicate_toast(request, form=None, error=None):
    if getattr(request, "_plate_duplicate_message_shown", False):
        return False

    candidates = []
    if form is not None:
        candidates.extend(form.errors.get('license_plate', []))
    if error is not None:
        candidates.append(str(error))

    for candidate in candidates:
        if _is_plate_duplicate_message(candidate):
            messages.error(request, "Plate number already exists.")
            request._plate_duplicate_message_shown = True
            return True

    return False
# -------------------------
# OCR ENDPOINT
# -------------------------
@login_required
@csrf_exempt
@require_POST
def ocr_process(request):
    """OCR endpoint for license scanning."""
    try:
        data = json.loads(request.body)
        image_data = data.get('image_data', '')

        if not image_data:
            return JsonResponse({'error': 'No image data provided.'})

        format, imgstr = image_data.split(';base64,')
        nparr = np.frombuffer(base64.b64decode(imgstr), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        raw_text = pytesseract.image_to_string(thresh)
        print("🧾 OCR RAW TEXT:", raw_text)
        text = re.sub(r'[^A-Za-z0-9\s:/-]', ' ', raw_text).upper()

        license_number = re.search(r'([A-Z]{1,2}\d{2,3}-\d{2}-\d{6,7})', text)
        if not license_number:
            license_number = re.search(r'(?:[A-Z]{3}-?\d{6,7})', text)

        name_match = re.search(r'([A-Z]+),\s*([A-Z]+)\s*([A-Z]*)', text)
        birthdate = re.search(r'(\d{4}/\d{2}/\d{2})', text)
        expiry = re.search(r'(\d{4}/\d{2}/\d{2})', text)

        result = {
            'license_number': license_number.group(0) if license_number else '',
            'last_name': name_match.group(1).title() if name_match else '',
            'first_name': name_match.group(2).title() if name_match else '',
            'middle_name': name_match.group(3).title() if name_match and name_match.group(3) else '',
            'birth_date': birthdate.group(0) if birthdate else '',
            'license_expiry': expiry.group(0) if expiry else '',
        }

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({'error': str(e)})


# -------------------------
# STAFF DASHBOARD
# -------------------------
@login_required
@user_passes_test(is_staff_admin_or_admin)
def staff_dashboard(request):
    """Main staff dashboard showing driver + vehicle registration quick links."""
    driver_form = DriverRegistrationForm(request.POST or None, request.FILES or None)
    vehicle_form = VehicleRegistrationForm(request.POST or None)

    if request.method == 'POST':
        if 'driver_submit' in request.POST:
            if driver_form.is_valid():
                driver_form.save()
                messages.success(request, "✅ Driver registered successfully!")
                # Redirect based on user role
                if request.user.role == 'admin':
                    return redirect('accounts:admin_dashboard')
                else:
                    return redirect('accounts:staff_dashboard')
            else:
                messages.error(request, "❌ Driver form contains errors.")

        elif 'vehicle_submit' in request.POST:
            if vehicle_form.is_valid():
                try:
                    vehicle = vehicle_form.save(commit=False)
                    cd = vehicle_form.cleaned_data

                    # ✅ Assign selected route
                    if cd.get('route'):
                        vehicle.route = cd['route']

                    # Other field validations (safeguard)
                    for field in ['cr_number', 'or_number', 'vin_number', 'year_model']:
                        if field in cd:
                            setattr(vehicle, field, cd.get(field) or getattr(vehicle, field))

                    vehicle.full_clean()
                    vehicle.save()
                    messages.success(request, f"✅ Vehicle '{vehicle.vehicle_name}' registered successfully!")
                    # Redirect based on user role
                    if request.user.role == 'admin':
                        return redirect('accounts:admin_dashboard')
                    else:
                        return redirect('accounts:staff_dashboard')
                except ValidationError as ve:
                    vehicle_form.add_error(None, ve)
                    maybe_show_plate_duplicate_toast(request, error=ve)
                    messages.error(request, "❌ Invalid vehicle data.")
                except IntegrityError as ie:
                    if not maybe_show_plate_duplicate_toast(request, error=ie):
                        messages.error(request, f"❌ Database error: {ie}")
                except Exception as e:
                    messages.error(request, f"❌ Unexpected error: {e}")
            else:
                maybe_show_plate_duplicate_toast(request, form=vehicle_form)
                messages.error(request, "❌ Vehicle form contains errors.")

    context = {
        'driver_form': driver_form,
        'vehicle_form': vehicle_form,
        'total_drivers': Driver.objects.count(),
        'total_vehicles': Vehicle.objects.count(),
    }
    return render(request, 'accounts/staff_dashboard.html', context)


# -------------------------
# VEHICLE REGISTRATION (page)
# -------------------------
@login_required
@user_passes_test(is_staff_admin_or_admin)
def vehicle_registration(request):
    form = VehicleRegistrationForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            try:
                vehicle = form.save(commit=False)
                cd = form.cleaned_data

                # ✅ Assign route
                if cd.get('route'):
                    vehicle.route = cd['route']

                for field in ['cr_number', 'or_number', 'vin_number', 'year_model']:
                    if field in cd:
                        setattr(vehicle, field, cd.get(field) or getattr(vehicle, field))

                vehicle.full_clean()
                vehicle.save()
                messages.success(request, f"✅ Vehicle '{vehicle.vehicle_name}' registered successfully!")
                return redirect('vehicles:register_vehicle')
            except ValidationError as ve:
                form.add_error(None, ve)
                maybe_show_plate_duplicate_toast(request, error=ve)
                messages.error(request, "❌ Invalid vehicle data.")
            except IntegrityError as ie:
                if not maybe_show_plate_duplicate_toast(request, error=ie):
                    messages.error(request, f"❌ Database error: {ie}")
            except Exception as e:
                messages.error(request, f"❌ Unexpected error: {e}")
        else:
            maybe_show_plate_duplicate_toast(request, form=form)
            messages.error(request, "❌ Please correct the errors.")

    vehicles = Vehicle.objects.select_related('assigned_driver', 'route').all().order_by('-date_registered')
    return render(request, 'vehicles/register_vehicle.html', {'form': form, 'vehicles': vehicles})


# -------------------------
# AJAX ENDPOINTS
# -------------------------
@login_required
@user_passes_test(is_staff_admin_or_admin)
@csrf_exempt
def ajax_register_driver(request):
    if request.method == 'POST':
        form = DriverRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            driver = form.save()
            return JsonResponse({'success': True, 'message': f"✅ Driver '{driver.first_name} {driver.last_name}' registered successfully!"})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    return JsonResponse({'success': False, 'message': 'Invalid request.'})


@login_required
@user_passes_test(is_staff_admin_or_admin)
@csrf_exempt
def ajax_register_vehicle(request):
    if request.method == 'POST':
        form = VehicleRegistrationForm(request.POST)
        if form.is_valid():
            try:
                vehicle = form.save(commit=False)
                cd = form.cleaned_data

                # ✅ Assign route
                if cd.get('route'):
                    vehicle.route = cd['route']

                for field in ['cr_number', 'or_number', 'vin_number', 'year_model']:
                    if field in cd:
                        setattr(vehicle, field, cd.get(field) or getattr(vehicle, field))

                vehicle.full_clean()
                vehicle.save()
                return JsonResponse({'success': True, 'message': f"✅ Vehicle '{vehicle.vehicle_name}' registered successfully!"})
            except ValidationError as ve:
                return JsonResponse({'success': False, 'errors': ve.message_dict})
            except Exception as e:
                return JsonResponse({'success': False, 'errors': str(e)})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    return JsonResponse({'success': False, 'message': 'Invalid request.'})


# -------------------------
# DEDICATED STAFF PAGES
# -------------------------
@login_required
@user_passes_test(is_staff_admin_or_admin)
def register_driver(request):
    """
    Register a new driver with comprehensive error handling.
    Shows specific errors for each field validation failure.
    """
    if request.method == 'POST':
        form = DriverRegistrationForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Save the driver
                driver = form.save()
                
                # Success message with driver details
                messages.success(
                    request,
                    f"✅ Driver registered successfully! "
                    f"Name: {driver.first_name} {driver.last_name} | "
                    f"ID: {driver.driver_id} | "
                    f"License: {driver.license_number}"
                )
                return redirect('vehicles:registered_drivers')
                
            except ValidationError as ve:
                # Model-level validation errors
                if hasattr(ve, 'message_dict'):
                    for field, errors in ve.message_dict.items():
                        field_label = field.replace('_', ' ').title()
                        for error in errors:
                            messages.error(request, f"❌ {field_label}: {error}")
                else:
                    messages.error(request, f"❌ Validation Error: {str(ve)}")
                    
            except Exception as e:
                # Unexpected errors
                messages.error(
                    request,
                    f"❌ Unexpected error while saving driver: {str(e)}"
                )
        else:
            # Form validation errors - Show each error specifically
            error_list = format_form_errors(form, "Driver Registration")
            missing_fields = []

            for field_name in form.fields:
                if form.errors.get(field_name):
                    continue
                field = form.fields[field_name]
                if getattr(field, "required", False):
                    raw_value = request.POST.get(field_name)
                    if raw_value is None or not str(raw_value).strip():
                        missing_fields.append(field.label or field_name.replace("_", " ").title())

            if missing_fields:
                for label in missing_fields:
                    messages.error(
                        request,
                        f"❌ {label}: This field is required but was left blank."
                    )

            if error_list or missing_fields:
                messages.error(
                    request,
                    "❌ Driver registration failed. Please see the field-specific details above."
                )
            else:
                messages.error(
                    request,
                    "❌ Driver registration failed. Please check all required fields and try again."
                )
    else:
        form = DriverRegistrationForm()
    
    # Get total drivers for display
    total_drivers = Driver.objects.count()
    
    context = {
        'form': form,
        'total_drivers': total_drivers,
    }
    
    return render(request, 'vehicles/register_driver.html', context)


@login_required
@user_passes_test(is_staff_admin_or_admin)
def driver_edit_form(request, driver_id):
    driver = get_object_or_404(Driver, pk=driver_id)
    form = DriverEditForm(instance=driver)
    html = _render_driver_edit_partial(request, form, driver)
    return JsonResponse({'html': html})


@login_required
@user_passes_test(is_staff_admin_or_admin)
def edit_driver(request, driver_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    driver = get_object_or_404(Driver, pk=driver_id)
    form = DriverEditForm(request.POST, request.FILES, instance=driver)

    if form.is_valid():
        try:
            form.save()
        except IntegrityError as ie:
            form.add_error(None, str(ie))
        except ValidationError as ve:
            form.add_error(None, ve)
        else:
            messages.success(request, "✅ Driver details updated successfully.")
            return JsonResponse({'success': True})

    html = _render_driver_edit_partial(request, form, driver)
    return JsonResponse({'success': False, 'html': html})


@login_required
@user_passes_test(is_staff_admin_or_admin)
def register_vehicle(request):
    """
    Register a new vehicle with comprehensive error handling.
    Shows specific errors for each field validation failure.
    """
    if request.method == 'POST':
        form = VehicleRegistrationForm(request.POST)
        
        if form.is_valid():
            try:
                vehicle = form.save(commit=False)
                cd = form.cleaned_data

                required_fields = {
                    'cr_number': 'CR Number',
                    'or_number': 'OR Number',
                    'vin_number': 'VIN Number',
                    'year_model': 'Year Model',
                    'registration_number': 'Registration Number',
                    'registration_expiry': 'Registration Expiry',
                    'license_plate': 'License Plate',
                    'vehicle_type': 'Vehicle Type',
                    'ownership_type': 'Ownership Type',
                    'assigned_driver': 'Assigned Driver',
                }

                missing_required = [
                    label for field, label in required_fields.items()
                    if not cd.get(field)
                ]

                if missing_required:
                    for label in missing_required:
                        messages.error(request, f"❌ {label} is required but missing.")
                    messages.error(
                        request,
                        "❌ Vehicle registration failed. Please complete the required fields above."
                    )
                    raise ValidationError("Missing required fields.")

                if cd.get('route'):
                    vehicle.route = cd['route']

                vehicle.save()
                messages.success(
                    request,
                    f"✅ Vehicle '{vehicle.vehicle_name}' registered successfully! "
                    f"Plate: {vehicle.license_plate}"
                )
                return redirect('vehicles:registered_vehicles')

            except ValidationError as ve:
                handle_vehicle_validation_errors(request, form, ve)
                    
            except IntegrityError as ie:
                if not maybe_show_plate_duplicate_toast(request, error=ie):
                    messages.error(request, f"❌ Database error: {ie}")
                
            except Exception as e:
                # Unexpected errors
                messages.error(
                    request,
                    f"❌ Unexpected error while saving vehicle: {str(e)}"
                )
        else:
            # Form validation errors - Show each error specifically
            maybe_show_plate_duplicate_toast(request, form=form)
            error_list = format_form_errors(form, "Vehicle Registration")
            
            if error_list:
                # Show a summary message
                messages.error(
                    request,
                    f"❌ Vehicle registration failed. Please correct {len(error_list)} error(s) below:"
                )
                
                # Show each specific error
                for error_msg in error_list:
                    messages.error(request, error_msg)
            else:
                # Fallback if no specific errors found
                messages.error(
                    request,
                    "❌ Vehicle registration failed. Please check all required fields and try again."
                )
    else:
        form = VehicleRegistrationForm()
    
    # Get vehicles for display
    vehicles = Vehicle.objects.select_related('assigned_driver', 'route').order_by('-date_registered')
    total_vehicles = vehicles.count()
    
    context = {
        'form': form,
        'vehicles': vehicles,
        'total_vehicles': total_vehicles,
    }
    
    return render(request, 'vehicles/register_vehicle.html', context)


@login_required
@user_passes_test(is_staff_admin_or_admin)
def vehicle_edit_form(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    form = VehicleRegistrationForm(instance=vehicle)
    html = _render_vehicle_edit_partial(request, form, vehicle)
    return JsonResponse({'html': html})


@login_required
@user_passes_test(is_staff_admin_or_admin)
def edit_vehicle(request, vehicle_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    form = VehicleRegistrationForm(request.POST, instance=vehicle)

    if form.is_valid():
        updated_vehicle = form.save(commit=False)
        try:
            updated_vehicle.full_clean()
            updated_vehicle.save()
        except IntegrityError as ie:
            form.add_error(None, str(ie))
        except ValidationError as ve:
            form.add_error(None, ve)
        else:
            messages.success(
                request,
                f"✅ Vehicle '{updated_vehicle.license_plate}' updated successfully."
            )
            return JsonResponse({'success': True})

    html = _render_vehicle_edit_partial(request, form, vehicle)
    return JsonResponse({'success': False, 'html': html})


# -------------------------
# WALLET & DEPOSITS
# -------------------------
@login_required
def get_wallet_balance(request, driver_id):
    try:
        driver = get_object_or_404(Driver, pk=driver_id)
        vehicle = driver.vehicles.first()
        if not vehicle:
            return JsonResponse({'success': False, 'message': 'Driver has no vehicle.'})
        wallet = getattr(vehicle, 'wallet', None) or Wallet.objects.create(vehicle=vehicle)
        return JsonResponse({'success': True, 'balance': float(wallet.balance)})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@user_passes_test(is_staff_admin_or_admin)
def vehicle_qr_view(request, vehicle_id):
    user_role = getattr(request.user, 'role', '')
    if not (request.user.is_staff or user_role in ['staff_admin', 'admin']):
        messages.error(request, "You do not have permission to view this page.")
        return redirect('vehicles:register_vehicle')
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    return render(request, 'vehicles/qr_detail.html', {'vehicle': vehicle})


@login_required
@csrf_exempt
def ajax_deposit(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})
    driver_id = request.POST.get('driver') or request.POST.get('driver_id')
    amount = request.POST.get('amount')
    payment_method = request.POST.get('payment_method', 'manual')
    if not driver_id or not amount:
        return JsonResponse({'success': False, 'message': 'Missing driver or amount.'})
    try:
        driver = get_object_or_404(Driver, pk=driver_id)
        vehicle = driver.vehicles.first()
        if not vehicle:
            return JsonResponse({'success': False, 'message': 'Driver has no vehicle.'})
        wallet = getattr(vehicle, 'wallet', None) or Wallet.objects.create(vehicle=vehicle)
        amt = Decimal(amount)
        if amt <= 0:
            return JsonResponse({'success': False, 'message': 'Amount must be greater than zero.'})
        deposit = Deposit.objects.create(wallet=wallet, amount=amt, payment_method=payment_method)
        return JsonResponse({'success': True, 'message': 'Deposit recorded.', 'new_balance': float(wallet.balance)})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# -------------------------
# REGISTERED VEHICLES / DRIVERS
# -------------------------
@login_required
@user_passes_test(is_staff_admin_or_admin)
def registered_vehicles(request):
    vehicle_qs = (
        Vehicle.objects
        .select_related('assigned_driver')
        .order_by('-date_registered')
    )

    paginator = Paginator(vehicle_qs, 16)  # ✅ 16 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'vehicles/registered_vehicles.html',
        {
            'page_obj': page_obj
        }
    )



@login_required
@user_passes_test(is_staff_admin_or_admin)
def registered_drivers(request):
    query = request.GET.get('q', '').strip()

    driver_qs = Driver.objects.all().order_by('-id')

    if query:
        driver_qs = driver_qs.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(license_number__icontains=query) |
            Q(mobile_number__icontains=query)
        )

    paginator = Paginator(driver_qs, 16)  # ✅ 16 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'vehicles/registered_drivers.html',
        {
            'page_obj': page_obj,
            'query': query  # ✅ keep search text
        }
    )



@login_required
def get_vehicles_by_driver(request, driver_id):
    vehicles = Vehicle.objects.filter(assigned_driver_id=driver_id)
    data = {"vehicles": [{"id": v.id, "license_plate": v.license_plate, "vehicle_name": v.vehicle_name} for v in vehicles]}
    return JsonResponse(data)

@login_required
@user_passes_test(is_admin)
@require_POST
@never_cache
def delete_driver(request, driver_id):
    try:
        driver = get_object_or_404(Driver, id=driver_id)
        driver_name = f"{driver.first_name} {driver.last_name}"
        driver.delete()

        # ✅ Django toast message (stored in session)
        messages.success(request, f"Driver '{driver_name}' deleted successfully.")

        # ✅ AJAX response (used by JS toast)
        return JsonResponse({
            "success": True,
            "message": f"Driver '{driver_name}' deleted successfully."
        })

    except Exception as e:
        messages.error(request, str(e))
        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=500
        )


@login_required
@user_passes_test(is_admin)
@require_POST
@never_cache
def delete_vehicle(request, vehicle_id):
    try:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        vehicle_name = vehicle.vehicle_name
        vehicle.delete()

        # ✅ Django toast message
        messages.success(request, f"Vehicle '{vehicle_name}' deleted successfully.")

        return JsonResponse({
            "success": True,
            "message": f"Vehicle '{vehicle_name}' deleted successfully."
        })

    except Exception as e:
        messages.error(request, str(e))
        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=500
        )
# -------------------------
# QR ENTRY & EXIT HANDLERS
# -------------------------
@login_required
@csrf_exempt
def qr_entry(request):
    """
    Triggered when vehicle QR is scanned on ENTRY.
    Sets status to 'boarding', computes departure_time (+30 mins default),
    and logs QueueHistory.
    """
    qr_value = request.POST.get('qr_value')
    if not qr_value:
        return JsonResponse({'success': False, 'message': 'Missing QR value.'})

    try:
        vehicle = get_object_or_404(Vehicle, qr_value=qr_value)
        now = timezone.now()
        vehicle.status = 'boarding'
        vehicle.last_enter_time = now
        vehicle.departure_time = now + timezone.timedelta(minutes=30)  # default waiting time
        vehicle.save(update_fields=['status', 'last_enter_time', 'departure_time'])

        QueueHistory.objects.create(
            vehicle=vehicle,
            driver=vehicle.assigned_driver,
            action='enter',
            departure_time_snapshot=vehicle.departure_time,
            wallet_balance_snapshot=vehicle.wallet.balance,
            fee_charged=vehicle.route.base_fare if vehicle.route else None,
        )
        return JsonResponse({'success': True, 'message': f"{vehicle.license_plate} entered terminal.", 'departure_time': vehicle.departure_time})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@csrf_exempt
def qr_exit(request):
    """
    Triggered when vehicle QR is scanned on EXIT.
    Sets status to 'departed', keeps it for 10 mins, logs QueueHistory.
    """
    qr_value = request.POST.get('qr_value')
    if not qr_value:
        return JsonResponse({'success': False, 'message': 'Missing QR value.'})

    try:
        vehicle = get_object_or_404(Vehicle, qr_value=qr_value)
        now = timezone.now()
        vehicle.status = 'departed'
        vehicle.last_exit_time = now
        vehicle.save(update_fields=['status', 'last_exit_time'])

        QueueHistory.objects.create(
            vehicle=vehicle,
            driver=vehicle.assigned_driver,
            action='exit',
            departure_time_snapshot=vehicle.departure_time,
            wallet_balance_snapshot=vehicle.wallet.balance,
        )

        return JsonResponse({'success': True, 'message': f"{vehicle.license_plate} departed terminal."})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# -------------------------
# ADMIN DASHBOARD DATA (7-day trend)
# -------------------------
@login_required
@user_passes_test(is_admin)
def admin_dashboard_data(request):
    """Return JSON with 7-day profit trend and live stats."""
    from django.db.models.functions import TruncDate
    from datetime import timedelta

    now = timezone.now()
    seven_days_ago = now - timedelta(days=6)

    # Group deposits by date
    daily_profits = (
        Deposit.objects.filter(created_at__date__gte=seven_days_ago.date())
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )

    # Ensure we produce labels for each of the last 7 days (even if 0)
    labels = []
    data_points = []
    for i in range(6, -1, -1):  # 6 -> 0 (six days ago .. today)
        d = (now - timedelta(days=i)).date()
        labels.append(d.strftime('%b %d'))
        matching = next((item for item in daily_profits if item['day'].date() == d), None)
        data_points.append(float(matching['total']) if matching else 0.0)

    total_drivers = Driver.objects.count()
    total_vehicles = Vehicle.objects.count()
    total_deposits = Deposit.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_wallets = Wallet.objects.aggregate(total=Sum('balance'))['total'] or 0

    recent_deposits = list(
        Deposit.objects.select_related('wallet__vehicle')
        .order_by('-created_at')[:5]
        .values('reference_number', 'amount', 'created_at', 'wallet__vehicle__license_plate')
    )

    recent_queues = list(
        QueueHistory.objects.select_related('vehicle')
        .order_by('-timestamp')[:5]
        .values('vehicle__license_plate', 'action', 'timestamp')
    )

    data = {
        'total_drivers': total_drivers,
        'total_vehicles': total_vehicles,
        'total_profit': float(total_deposits),
        'wallet_total': float(total_wallets),
        'recent_deposits': recent_deposits,
        'recent_queues': recent_queues,
        'chart_labels': labels,
        'chart_data': data_points,
    }
    return JsonResponse(data)


# -------------------------
# QUEUE HISTORY VIEW (for admin)
# -------------------------
@login_required
@user_passes_test(is_admin)
def queue_history(request):
    history = QueueHistory.objects.select_related('vehicle', 'driver').order_by('-timestamp')
    paginator = Paginator(history, 20)
    page = paginator.get_page(request.GET.get('page'))
    return redirect('terminal:transactions')

