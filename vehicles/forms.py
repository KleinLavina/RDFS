from django import forms
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date
import re
from .models import Driver, Vehicle, Deposit, Wallet, Route


# ======================================================
# VEHICLE REGISTRATION FORM - WITH SPECIFIC ERROR MESSAGES
# ======================================================
class VehicleRegistrationForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'vehicle_name',
            'vehicle_type',
            'ownership_type',
            'assigned_driver',
            'route',
            'cr_number',
            'or_number',
            'vin_number',
            'year_model',
            'registration_number',
            'registration_expiry',
            'license_plate',
            'seat_capacity',
        ]
        widgets = {
            'vehicle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-select'}),
            'ownership_type': forms.Select(attrs={'class': 'form-select'}),
            'assigned_driver': forms.Select(attrs={'class': 'form-select'}),
            'route': forms.Select(attrs={'class': 'form-select'}),
            'cr_number': forms.TextInput(attrs={'class': 'form-control'}),
            'or_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vin_number': forms.TextInput(attrs={'class': 'form-control'}),
            'year_model': forms.NumberInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'license_plate': forms.TextInput(attrs={'class': 'form-control'}),
            'seat_capacity': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        error_messages = {
            'vehicle_type': {
                'required': '❌ Vehicle type is required. Please select a vehicle type.',
            },
            'ownership_type': {
                'required': '❌ Ownership type is required. Please select an ownership type.',
            },
            'assigned_driver': {
                'required': '❌ Assigned driver is required. Please select a driver.',
            },
            'cr_number': {
                'required': '❌ CR (Certificate of Registration) number is required.',
                'unique': '❌ This CR number is already registered in the system.',
            },
            'or_number': {
                'required': '❌ OR (Official Receipt) number is required.',
                'unique': '❌ This OR number is already registered in the system.',
            },
            'vin_number': {
                'required': '❌ VIN (Vehicle Identification Number) is required.',
                'unique': '❌ This VIN is already registered in the system.',
            },
            'year_model': {
                'required': '❌ Year model is required.',
                'invalid': '❌ Invalid year format. Please enter a valid year.',
            },
            'registration_number': {
                'required': '❌ Registration number is required.',
                'unique': '❌ This registration number is already in use.',
            },
            'registration_expiry': {
                'required': '❌ Registration expiry date is required.',
                'invalid': '❌ Invalid date format. Please select a valid date.',
            },
            'license_plate': {
                'required': '❌ License plate is required.',
                'unique': '❌ This license plate is already registered in the system.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        required_fields = [
            'vehicle_type', 'ownership_type', 'assigned_driver', 
            'cr_number', 'or_number', 'vin_number', 'year_model',
            'registration_number', 'registration_expiry', 'license_plate'
        ]
        
        for field_name in required_fields:
            self.fields[field_name].required = True
            
        # Set optional fields
        self.fields['vehicle_name'].required = False
        self.fields['route'].required = False
        self.fields['seat_capacity'].required = False
        
        # Filter querysets
        self.fields['route'].queryset = Route.objects.filter(active=True)
        self.fields['assigned_driver'].queryset = Driver.objects.all().order_by('first_name', 'last_name')
        
        # Add empty labels for dropdowns
        self.fields['vehicle_type'].empty_label = "Select Vehicle Type"
        self.fields['ownership_type'].empty_label = "Select Ownership Type"
        self.fields['assigned_driver'].empty_label = "Select Driver"
        self.fields['route'].empty_label = "Select Route (Optional)"

    # --------------------------------------------------
    # FIELD VALIDATIONS
    # --------------------------------------------------
    def clean_vehicle_name(self):
        value = self.cleaned_data.get('vehicle_name', '').strip()
        if value and len(value) > 100:
            raise ValidationError(
                f"❌ Vehicle name is too long. Maximum 100 characters allowed (currently {len(value)} characters)."
            )
        return value if value else "Unnamed Vehicle"

    def clean_cr_number(self):
        value = self.cleaned_data.get('cr_number')
        if not value or not str(value).strip():
            raise ValidationError("❌ CR (Certificate of Registration) number is required.")
        
        value = str(value).strip().upper()
        
        if len(value) < 5:
            raise ValidationError(
                f"❌ CR number is too short. Minimum 5 characters required (currently {len(value)} characters)."
            )
        
        if len(value) > 50:
            raise ValidationError(
                f"❌ CR number is too long. Maximum 50 characters allowed (currently {len(value)} characters)."
            )
        
        # Check uniqueness excluding current instance
        if self.instance.pk:
            if Vehicle.objects.exclude(pk=self.instance.pk).filter(cr_number=value).exists():
                raise ValidationError(
                    f"❌ CR number '{value}' is already registered to another vehicle."
                )
        else:
            if Vehicle.objects.filter(cr_number=value).exists():
                raise ValidationError(
                    f"❌ CR number '{value}' is already registered in the system."
                )
        
        return value

    def clean_or_number(self):
        value = self.cleaned_data.get('or_number')
        if not value or not str(value).strip():
            raise ValidationError("❌ OR (Official Receipt) number is required.")
        
        value = str(value).strip().upper()
        
        if len(value) < 5:
            raise ValidationError(
                f"❌ OR number is too short. Minimum 5 characters required (currently {len(value)} characters)."
            )
        
        if len(value) > 50:
            raise ValidationError(
                f"❌ OR number is too long. Maximum 50 characters allowed (currently {len(value)} characters)."
            )
        
        # Check uniqueness
        if self.instance.pk:
            if Vehicle.objects.exclude(pk=self.instance.pk).filter(or_number=value).exists():
                raise ValidationError(
                    f"❌ OR number '{value}' is already registered to another vehicle."
                )
        else:
            if Vehicle.objects.filter(or_number=value).exists():
                raise ValidationError(
                    f"❌ OR number '{value}' is already registered in the system."
                )
        
        return value

    def clean_vin_number(self):
        value = self.cleaned_data.get('vin_number')
        if not value or not str(value).strip():
            raise ValidationError("❌ VIN (Vehicle Identification Number) is required.")
        
        value = str(value).strip().upper()
        
        if len(value) != 17:
            raise ValidationError(
                f"❌ Invalid VIN number. VIN must be exactly 17 characters (currently {len(value)} characters)."
            )
        
        # VIN validation: no I, O, Q letters
        if not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', value):
            raise ValidationError(
                "❌ Invalid VIN format. VIN must contain 17 alphanumeric characters (excluding I, O, Q)."
            )
        
        # Check uniqueness
        if self.instance.pk:
            if Vehicle.objects.exclude(pk=self.instance.pk).filter(vin_number=value).exists():
                raise ValidationError(
                    f"❌ VIN '{value}' is already registered to another vehicle."
                )
        else:
            if Vehicle.objects.filter(vin_number=value).exists():
                raise ValidationError(
                    f"❌ VIN '{value}' is already registered in the system."
                )
        
        return value

    def clean_year_model(self):
        year = self.cleaned_data.get('year_model')
        if not year:
            raise ValidationError("❌ Year model is required. Please enter the vehicle's year model.")
        
        try:
            year = int(year)
            current_year = timezone.now().year
            
            if year < 1886:
                raise ValidationError(
                    f"❌ Invalid year. Vehicles didn't exist before 1886. You entered: {year}"
                )
            
            if year > current_year + 1:
                raise ValidationError(
                    f"❌ Invalid year. Year cannot be more than {current_year + 1}. You entered: {year}"
                )
            
            # Warn about very old vehicles
            if year < 1980:
                # This is just informational, not blocking
                pass
            
            return year
            
        except (ValueError, TypeError):
            raise ValidationError(
                "❌ Invalid year format. Please enter a valid 4-digit year (e.g., 2024)."
            )

    def clean_seat_capacity(self):
        seats = self.cleaned_data.get('seat_capacity')
        
        if seats is not None and str(seats).strip():
            try:
                seats = int(seats)
                
                if seats <= 0:
                    raise ValidationError(
                        "❌ Seat capacity must be greater than zero."
                    )
                
                if seats > 100:
                    raise ValidationError(
                        f"❌ Seat capacity seems unrealistic. Maximum 100 seats allowed (you entered: {seats})."
                    )
                
                return seats
                
            except (ValueError, TypeError):
                raise ValidationError(
                    "❌ Invalid seat capacity. Please enter a valid number."
                )
        
        return None

    def clean_registration_expiry(self):
        expiry = self.cleaned_data.get('registration_expiry')
        if not expiry:
            raise ValidationError("❌ Registration expiry date is required.")
        
        today = date.today()
        
        if expiry < today:
            days_expired = (today - expiry).days
            raise ValidationError(
                f"❌ Registration has expired. Expired on {expiry.strftime('%B %d, %Y')} "
                f"({days_expired} day{'s' if days_expired != 1 else ''} ago). "
                f"Please renew before registering."
            )
        
        # Warn if expiring soon (within 30 days)
        days_until_expiry = (expiry - today).days
        if days_until_expiry <= 30:
            # Note: This could be added as a warning message in the view
            pass
        
        return expiry

    def clean_license_plate(self):
        license_plate = self.cleaned_data.get('license_plate')
        if not license_plate or not str(license_plate).strip():
            raise ValidationError("❌ License plate is required.")
        
        value = str(license_plate).strip().upper()
        
        # Basic validation
        if len(value) < 2:
            raise ValidationError(
                f"❌ License plate is too short. Minimum 2 characters required."
            )
        
        if len(value) > 12:
            raise ValidationError(
                f"❌ License plate is too long. Maximum 12 characters allowed (currently {len(value)} characters)."
            )
        
        # Format validation: letters, numbers, spaces, hyphens only
        if not re.match(r'^[A-Z0-9][A-Z0-9\s\-]{1,11}$', value):
            raise ValidationError(
                "❌ Invalid license plate format. Use only letters, numbers, spaces, or hyphens."
            )
        
        # Check uniqueness
        if self.instance.pk:
            if Vehicle.objects.exclude(pk=self.instance.pk).filter(license_plate=value).exists():
                raise ValidationError(
                    f"❌ License plate '{value}' is already registered to another vehicle."
                )
        else:
            if Vehicle.objects.filter(license_plate=value).exists():
                raise ValidationError(
                    f"❌ License plate '{value}' is already registered in the system."
                )
        
        return value

    def clean_registration_number(self):
        reg_num = self.cleaned_data.get('registration_number')
        if not reg_num or not str(reg_num).strip():
            raise ValidationError("❌ Registration number is required.")
        
        value = str(reg_num).strip().upper()
        
        if len(value) < 5:
            raise ValidationError(
                f"❌ Registration number is too short. Minimum 5 characters required (currently {len(value)} characters)."
            )
        
        if len(value) > 50:
            raise ValidationError(
                f"❌ Registration number is too long. Maximum 50 characters allowed (currently {len(value)} characters)."
            )
        
        # Check uniqueness
        if self.instance.pk:
            if Vehicle.objects.exclude(pk=self.instance.pk).filter(registration_number=value).exists():
                raise ValidationError(
                    f"❌ Registration number '{value}' is already registered to another vehicle."
                )
        else:
            if Vehicle.objects.filter(registration_number=value).exists():
                raise ValidationError(
                    f"❌ Registration number '{value}' is already registered in the system."
                )
        
        return value

    def clean(self):
        cleaned_data = super().clean()
        
        # Cross-field validation: Check if driver already has a vehicle
        assigned_driver = cleaned_data.get('assigned_driver')
        if assigned_driver:
            existing_vehicles = Vehicle.objects.filter(assigned_driver=assigned_driver)
            if self.instance.pk:
                existing_vehicles = existing_vehicles.exclude(pk=self.instance.pk)
            
            if existing_vehicles.exists():
                vehicle_list = ", ".join([v.license_plate for v in existing_vehicles[:3]])
                self.add_error('assigned_driver', 
                    f"⚠️ Warning: Driver {assigned_driver.first_name} {assigned_driver.last_name} "
                    f"already has {existing_vehicles.count()} vehicle(s) assigned: {vehicle_list}"
                )
        
        return cleaned_data


# ======================================================
# DRIVER REGISTRATION FORM - WITH SPECIFIC ERROR MESSAGES
# ======================================================
class DriverRegistrationForm(forms.ModelForm):
    BLOOD_TYPE_CHOICES = [
        ('', 'Select Blood Type'),
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('N/A', 'N/A'),
    ]

    driver_photo = forms.ImageField(
        required=True,
        label="Driver Photo",
        error_messages={
            "required": "❌ Driver photo is required for identity verification.",
            "invalid": "❌ Invalid image file.",
            "missing": "❌ No photo was uploaded.",
            "empty": "❌ The uploaded photo file is empty."
        }
    )

    class Meta:
        model = Driver
        # 🔒 license_type is NOT included
        exclude = [
            'driver_id',
            'license_type',   # 🔒 LOCKED AT MODEL LEVEL
            'license_image',
            'house_number',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'suffix': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'birth_place': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'street': forms.TextInput(attrs={'class': 'form-control'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'city_municipality': forms.TextInput(attrs={'class': 'form-control'}),
            'province': forms.TextInput(attrs={'class': 'form-control'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control'}),
            'license_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_relationship': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Blood type (explicit choice field)
        self.fields['blood_type'] = forms.ChoiceField(
            choices=self.BLOOD_TYPE_CHOICES,
            widget=forms.Select(attrs={'class': 'form-select'}),
            label="Blood Type",
            required=True,
            error_messages={
                'required': '❌ Blood type is required.',
                'invalid_choice': '❌ Invalid blood type.',
            }
        )

    # 🔐 MODEL ENFORCES license_type — NO FORM VALIDATION NEEDED

    # -----------------------------
    # VALIDATIONS (UNCHANGED)
    # -----------------------------
    def clean_driver_photo(self):
        photo = self.cleaned_data.get('driver_photo')
        if not photo:
            raise ValidationError("❌ Driver photo is required.")
        if hasattr(photo, 'content_type') and not photo.content_type.startswith("image/"):
            raise ValidationError("❌ Invalid file type. Must be an image.")
        if hasattr(photo, 'size') and photo.size > 5 * 1024 * 1024:
            raise ValidationError("❌ Photo is too large. Maximum 5MB allowed.")
        return photo

    def clean_first_name(self):
        value = self.cleaned_data.get('first_name', '').strip()
        if not value:
            raise ValidationError("❌ First name is required.")
        if len(value) < 2:
            raise ValidationError("❌ First name too short.")
        if not re.match(r'^[a-zA-Z\s\-\.]+$', value):
            raise ValidationError("❌ First name contains invalid characters.")
        return value

    def clean_last_name(self):
        value = self.cleaned_data.get('last_name', '').strip()
        if not value:
            raise ValidationError("❌ Last name is required.")
        if len(value) < 2:
            raise ValidationError("❌ Last name too short.")
        if not re.match(r'^[a-zA-Z\s\-\.]+$', value):
            raise ValidationError("❌ Last name contains invalid characters.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        mobile = cleaned_data.get('mobile_number')
        emergency = cleaned_data.get('emergency_contact_number')
        if mobile and emergency:
            if re.sub(r'\D', '', mobile) == re.sub(r'\D', '', emergency):
                self.add_error(
                    'emergency_contact_number',
                    "⚠️ Emergency contact should be different from driver's number."
                )
        return cleaned_data



# ======================================================
# DEPOSIT FORM
# ======================================================
class DepositForm(forms.ModelForm):
    amount = forms.DecimalField(
        label="Deposit Amount (₱)",
        min_value=1,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter deposit amount'}),
        error_messages={
            'required': '❌ Deposit amount is required.',
            'invalid': '❌ Invalid amount format.',
            'min_value': '❌ Deposit must be at least ₱1.00.',
        }
    )

    class Meta:
        model = Deposit
        fields = ['amount']