import re
import uuid
import qrcode
from io import BytesIO

from django.core.files import File
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


# ======================================================
# ROUTE MODEL
# ======================================================
class Route(models.Model):
    """Represents a route, e.g., City A → City B."""
    name = models.CharField(max_length=150, unique=True, help_text="Example: City A - City B")
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    base_fare = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["origin", "destination"]

    def __str__(self):
        return f"{self.origin} → {self.destination}"


# ======================================================
# DRIVER MODEL
# ======================================================
class Driver(models.Model):
    # -----------------------------
    # CONSTANTS
    # -----------------------------
    LICENSE_PROFESSIONAL = "professional"

    # -----------------------------
    # DRIVER INFO
    # -----------------------------
    driver_id = models.CharField(max_length=100, unique=True, blank=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    suffix = models.CharField(max_length=10, blank=True, null=True)

    birth_date = models.DateField(blank=True, null=True)
    birth_place = models.CharField(max_length=150, blank=True, null=True)
    blood_type = models.CharField(max_length=5, blank=True, null=True)

    mobile_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    # -----------------------------
    # ADDRESS
    # -----------------------------
    house_number = models.CharField(max_length=50, blank=True, null=True)
    street = models.CharField(max_length=100, blank=True, null=True)
    barangay = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    city_municipality = models.CharField(max_length=100, blank=True, null=True)
    province = models.CharField(max_length=100, blank=True, null=True)

    # -----------------------------
    # LICENSE (LOCKED)
    # -----------------------------
    license_number = models.CharField(max_length=50, blank=True, null=True)
    license_expiry = models.DateField(blank=True, null=True)

    license_type = models.CharField(
        max_length=50,
        editable=False,                 # 🔒 NOT SHOWN IN FORMS/ADMIN
        default=LICENSE_PROFESSIONAL
    )

    # -----------------------------
    # DRIVER PHOTO (REQUIRED)
    # -----------------------------
    driver_photo = models.ImageField(
        upload_to="driver_img/",
        blank=False,
        null=False
    )

    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_number = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True, null=True)

    # -----------------------------
    # VALIDATION
    # -----------------------------
    def clean(self):
        errors = {}

        if self.license_type != self.LICENSE_PROFESSIONAL:
            errors["license_type"] = "Only Professional Driver’s Licenses are allowed."

        if not self.driver_photo:
            errors["driver_photo"] = "Driver photo is required."

        if errors:
            raise ValidationError(errors)

    # -----------------------------
    # SAVE
    # -----------------------------
    def save(self, *args, **kwargs):
        if not self.driver_id:
            self.driver_id = f"DRV-{uuid.uuid4().hex[:8].upper()}"

        # 🔐 FORCE VALUE EVEN IF TAMPERED
        self.license_type = self.LICENSE_PROFESSIONAL

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.driver_id})"



# ======================================================
# VEHICLE MODEL
# ======================================================
class Vehicle(models.Model):
    VEHICLE_TYPES = [
        ('jeepney', 'Jeepney'),
        ('van', 'Van'),
        ('bus', 'Bus'),
    ]

    OWNERSHIP_TYPES = [
        ('owned', 'Owned'),
        ('leased', 'Leased'),
        ('private', 'Private'),
    ]

    STATUS_CHOICES = [
        ('idle', 'Idle'),
        ('queued', 'Queued'),
        ('boarding', 'Boarding'),
        ('departed', 'Departed'),
    ]

    vehicle_name = models.CharField(max_length=100, default="Unnamed Vehicle")
    vehicle_type = models.CharField(max_length=50, choices=VEHICLE_TYPES)
    ownership_type = models.CharField(max_length=20, choices=OWNERSHIP_TYPES, default='owned')
    assigned_driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='vehicles')

    cr_number = models.CharField(max_length=50, unique=True, verbose_name="Registration Certificate Number")
    or_number = models.CharField(max_length=50, unique=True, verbose_name="Official Receipt Number")
    vin_number = models.CharField(max_length=17, unique=True, verbose_name="Vehicle Identification Number (VIN)")
    year_model = models.PositiveIntegerField()

    registration_number = models.CharField(max_length=50, unique=True)
    registration_expiry = models.DateField(blank=True, null=True)
    license_plate = models.CharField(max_length=50, unique=True)

    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True, related_name='vehicles')

    seat_capacity = models.PositiveIntegerField(blank=True, null=True)

    qr_code = models.ImageField(upload_to='qrcodes/', null=True, blank=True)
    qr_value = models.CharField(max_length=255, unique=True, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle')
    last_enter_time = models.DateTimeField(blank=True, null=True)
    last_exit_time = models.DateTimeField(blank=True, null=True)
    departure_time = models.DateTimeField(blank=True, null=True)

    date_registered = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # --------------------------------------------------
    # INTERNATIONAL VALIDATION
    # --------------------------------------------------
    def clean(self):
        errors = {}

        # Normalize values
        self.vin_number = self.vin_number.upper().strip() if self.vin_number else None
        self.license_plate = self.license_plate.upper().strip() if self.license_plate else None

        # VIN Number (global)
        if not self.vin_number or not str(self.vin_number).strip():
            errors['vin_number'] = "VIN number is required."
        elif not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', str(self.vin_number).strip()):
            errors['vin_number'] = "VIN number must be 17 alphanumeric characters (excluding I, O, Q)."

        # Registration Number (global) - Flexible format for both local and international
        if not self.registration_number or not str(self.registration_number).strip():
            errors['registration_number'] = "Registration number is required."

        # License plate (global)
        if not self.license_plate or not str(self.license_plate).strip():
            errors['license_plate'] = "License plate is required."
        elif not re.match(r'^[A-Z0-9][A-Z0-9\s\-]{1,11}$', str(self.license_plate).strip()):
            errors['license_plate'] = "License plate must be 2-12 characters and may include letters, numbers, spaces, or hyphens."

        # Year model (global)
        if self.year_model is None:
            errors['year_model'] = "Year model is required."
        else:
            try:
                year = int(self.year_model)
                current_year = timezone.now().year
                if year < 1886 or year > current_year + 1:
                    errors['year_model'] = f"Year must be between 1886 and {current_year + 1}."
            except (ValueError, TypeError):
                errors['year_model'] = "Please enter a valid year."

        # Seat capacity sanity
        if self.seat_capacity is not None and self.seat_capacity <= 0:
            errors['seat_capacity'] = "Seat capacity must be greater than zero."

        if errors:
            raise ValidationError(errors)

    # --------------------------------------------------
    # SAVE & QR GENERATION
    # --------------------------------------------------
    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)

        expected_qr_value = f"VEH-{self.id}-{self.license_plate}".replace(" ", "-").upper()
        if creating or self.qr_value != expected_qr_value:
            self.qr_value = expected_qr_value
            qr_image = qrcode.make(self.qr_value)

            buffer = BytesIO()
            qr_image.save(buffer, format='PNG')

            self.qr_code.save(
                f"vehicle_{self.id}_qr.png",
                File(buffer),
                save=False
            )
            super().save(update_fields=['qr_code', 'qr_value'])

    def __str__(self):
        route_display = str(self.route) if self.route else "No Route"
        return f"{self.vehicle_name} ({self.license_plate}) – {route_display}"


# ======================================================
# WALLET MODEL
# ======================================================
class Wallet(models.Model):
    vehicle = models.OneToOneField(Vehicle, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='PHP')
    status = models.CharField(max_length=10, default='active')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        driver = getattr(self.vehicle, 'assigned_driver', None)
        driver_name = f"{driver.first_name} {driver.last_name}" if driver else "Unknown Driver"
        return f"{driver_name}'s Wallet – {self.balance}"


# ======================================================
# DEPOSIT MODEL
# ======================================================
class Deposit(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference_number = models.CharField(max_length=50, unique=True, blank=True)

    status = models.CharField(max_length=15, default='successful')
    payment_method = models.CharField(max_length=20, default='cash')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if not self.reference_number:
            self.reference_number = f"DEP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        with transaction.atomic():
            super().save(*args, **kwargs)

            if is_new:
                Wallet.objects.filter(pk=self.wallet.pk).update(
                    balance=F('balance') + self.amount
                )
                self.wallet.refresh_from_db()

    def __str__(self):
        return f"Deposit {self.reference_number} – {self.amount}"


# ======================================================
# QUEUE HISTORY MODEL
# ======================================================
class QueueHistory(models.Model):
    ACTION_CHOICES = [
        ('enter', 'Enter'),
        ('exit', 'Exit'),
    ]

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='queue_history')
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)

    timestamp = models.DateTimeField(auto_now_add=True)
    departure_time_snapshot = models.DateTimeField(blank=True, null=True)
    wallet_balance_snapshot = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.vehicle} – {self.get_action_display()} @ {self.timestamp}"


# ======================================================
# SIGNALS
# ======================================================
@receiver(post_save, sender=Vehicle)
def create_wallet_for_vehicle(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(vehicle=instance)
    else:
        Wallet.objects.get_or_create(vehicle=instance)