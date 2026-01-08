from django import forms
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date
import re
from .models import Driver, Vehicle, Deposit, Wallet, Route
from terminal.models import SystemSettings


# ✅ Placeholder for potential extended form
class FullVehicleDetailsForm(forms.Form):
    pass


# ======================================================
# VEHICLE REGISTRATION FORM
# ======================================================
import re
from datetime import date
from django import forms
from django.core.exceptions import ValidationError

from .models import Vehicle, Route, Driver


class VehicleRegistrationForm(forms.ModelForm):
    # All pattern validations removed

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
            'registration_expiry': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        required_fields = [
            'vehicle_type', 'ownership_type', 'assigned_driver', 
            'cr_number', 'or_number', 'vin_number', 'year_model',
            'registration_number', 'registration_expiry', 'license_plate'
        ]
        
        # Set all required fields
        for field_name in required_fields:
            self.fields[field_name].required = True
            
        # Set optional fields
        self.fields['vehicle_name'].required = False
        self.fields['route'].required = False
        self.fields['seat_capacity'].required = False
        
        # Add form-control class to all fields
        for field_name, field in self.fields.items():
            if 'class' in field.widget.attrs:
                field.widget.attrs['class'] += ' form-control'
            else:
                field.widget.attrs['class'] = 'form-control'
        self.fields['route'].queryset = Route.objects.filter(active=True)
        self.fields['assigned_driver'].queryset = Driver.objects.all()

    # --------------------------------------------------
    # SIMPLIFIED FIELD VALIDATION
    # --------------------------------------------------
    def clean_cr_number(self):
        value = self.cleaned_data.get('cr_number')
        if not value or not str(value).strip():
            raise ValidationError("CR number is required.")
        return str(value).strip().upper()

    def clean_or_number(self):
        value = self.cleaned_data.get('or_number')
        if not value or not str(value).strip():
            raise ValidationError("OR number is required.")
        return str(value).strip().upper()

    def clean_vin_number(self):
        value = self.cleaned_data.get('vin_number')
        if not value or not str(value).strip():
            raise ValidationError("VIN number is required.")
        return str(value).strip().upper()

    def clean_year_model(self):
        year = self.cleaned_data.get('year_model')
        if not year:
            raise ValidationError("Year model is required.")
        try:
            year = int(year)
            current_year = timezone.now().year
            if year < 1886 or year > current_year + 1:
                raise ValidationError(f"Year must be between 1886 and {current_year + 1}.")
            return year
        except (ValueError, TypeError):
            raise ValidationError("Please enter a valid year.")

    def clean_seat_capacity(self):
        seats = self.cleaned_data.get('seat_capacity')
        if seats is not None and str(seats).strip():
            try:
                seats = int(seats)
                if seats <= 0:
                    raise ValidationError("Seat capacity must be greater than zero.")
                return seats
            except (ValueError, TypeError):
                raise ValidationError("Please enter a valid number of seats.")
        return None

    def clean_registration_expiry(self):
        expiry = self.cleaned_data.get('registration_expiry')
        if not expiry:
            raise ValidationError("Registration expiry date is required.")
        return expiry

    def clean_license_plate(self):
        license_plate = self.cleaned_data.get('license_plate')
        if not license_plate or not str(license_plate).strip():
            raise ValidationError("License plate is required.")
        return str(license_plate).strip().upper()

    def clean_registration_number(self):
        reg_num = self.cleaned_data.get('registration_number')
        if not reg_num or not str(reg_num).strip():
            raise ValidationError("Registration number is required.")
        return str(reg_num).strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        # Add any cross-field validation here if needed
        return cleaned_data


# ======================================================
# DRIVER REGISTRATION FORM
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

    # Hard-locked value
    PROFESSIONAL_VALUE = "professional"
    PROFESSIONAL_LABEL = "Professional Driver’s License"

    driver_photo = forms.ImageField(
        required=True,
        label="Driver Photo",
        error_messages={
            "required": "Driver photo is required for identity verification."
        }
    )

    license_type = forms.CharField(
        required=True,
        initial=PROFESSIONAL_VALUE,
        label="License Type",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "readonly": "readonly",
            }
        )
    )

    class Meta:
        model = Driver
        exclude = ['driver_id', 'license_image']  # license_image unchanged, not used here
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'suffix': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'required': 'required'}),
            'birth_place': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'required': 'required'}),
            'street': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'city_municipality': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'province': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'license_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'required': 'required'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'emergency_contact_relationship': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Blood type select
        self.fields['blood_type'] = forms.ChoiceField(
            choices=self.BLOOD_TYPE_CHOICES,
            widget=forms.Select(attrs={'class': 'form-select', 'required': 'required'}),
            label="Blood Type"
        )

        # Force professional license value at runtime (defense in depth)
        self.initial['license_type'] = self.PROFESSIONAL_VALUE
        self.fields['license_type'].help_text = self.PROFESSIONAL_LABEL

    # ------------------------------
    # FIELD VALIDATION
    # ------------------------------
    def clean_license_type(self):
        value = self.cleaned_data.get('license_type')
        if value != self.PROFESSIONAL_VALUE:
            raise ValidationError(
                "Only Professional Driver’s Licenses are allowed."
            )
        return self.PROFESSIONAL_VALUE

    def clean_driver_photo(self):
        photo = self.cleaned_data.get('driver_photo')
        if not photo:
            raise ValidationError("Driver photo is required.")

        if not photo.content_type.startswith("image/"):
            raise ValidationError("Uploaded file must be an image.")
        return photo

    # Keep your existing validators intact
    def clean_first_name(self):
        value = self.cleaned_data.get('first_name', '').strip()
        if len(value) < 2:
            raise ValidationError("First name must be at least 2 characters long.")
        return value

    def clean_last_name(self):
        value = self.cleaned_data.get('last_name', '').strip()
        if len(value) < 2:
            raise ValidationError("Last name must be at least 2 characters long.")
        return value

    def clean(self):
        cleaned_data = super().clean()
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
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter deposit amount'
        })
    )

    class Meta:
        model = Deposit
        fields = ['amount']