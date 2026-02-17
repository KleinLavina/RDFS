"""
Django management command to create mock data for Drivers and Vehicles.

STRICT REQUIREMENTS:
- Uses only existing model fields
- Creates 3 Drivers first
- Creates 3 Vehicles linked to those drivers (1:1 relationship)
- All expiry dates are set to future dates
- All required fields are populated
- No field invention or model modification
"""

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import io
from PIL import Image

from vehicles.models import Driver, Vehicle, Route, Wallet


class Command(BaseCommand):
    help = 'Create mock data: 3 Drivers and 3 Vehicles (1:1 relationship)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing mock data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('CREATING MOCK DATA FOR DRIVERS AND VEHICLES'))
        self.stdout.write(self.style.WARNING('=' * 70))

        # Clear existing data if requested
        if options['clear']:
            self.stdout.write(self.style.WARNING('\n🗑️  Clearing existing mock data...'))
            Vehicle.objects.all().delete()
            Driver.objects.all().delete()
            Route.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✅ Existing data cleared'))

        # Step 0: Create Routes (required for vehicles)
        self.stdout.write(self.style.WARNING('\n📍 Step 0: Creating Routes...'))
        routes = self._create_routes()
        self.stdout.write(self.style.SUCCESS(f'✅ Created {len(routes)} routes'))

        # Step 1: Create Drivers
        self.stdout.write(self.style.WARNING('\n👤 Step 1: Creating 3 Drivers...'))
        drivers = self._create_drivers()
        self.stdout.write(self.style.SUCCESS(f'✅ Created {len(drivers)} drivers'))

        # Step 2: Create Vehicles
        self.stdout.write(self.style.WARNING('\n🚗 Step 2: Creating 3 Vehicles...'))
        vehicles = self._create_vehicles(drivers, routes)
        self.stdout.write(self.style.SUCCESS(f'✅ Created {len(vehicles)} vehicles'))

        # Display Results
        self.stdout.write(self.style.WARNING('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('✅ MOCK DATA CREATION COMPLETE'))
        self.stdout.write(self.style.WARNING('=' * 70))

        self._display_results(drivers, vehicles)

    def _create_routes(self):
        """Create sample routes for vehicles."""
        routes_data = [
            {'name': 'Maasin - Sogod', 'origin': 'Maasin City', 'destination': 'Sogod', 'base_fare': Decimal('50.00')},
            {'name': 'Maasin - Bato', 'origin': 'Maasin City', 'destination': 'Bato', 'base_fare': Decimal('45.00')},
            {'name': 'Maasin - Hinunangan', 'origin': 'Maasin City', 'destination': 'Hinunangan', 'base_fare': Decimal('60.00')},
        ]

        routes = []
        for route_data in routes_data:
            route, created = Route.objects.get_or_create(
                name=route_data['name'],
                defaults=route_data
            )
            routes.append(route)
            if created:
                self.stdout.write(f'  ✓ Created route: {route.name}')
            else:
                self.stdout.write(f'  ℹ Route already exists: {route.name}')

        return routes

    def _create_drivers(self):
        """Create 3 drivers with all required fields."""
        # Future date for license expiry (2 years from now)
        future_expiry = date.today() + timedelta(days=730)

        drivers_data = [
            {
                'first_name': 'Juan',
                'middle_name': 'Santos',
                'last_name': 'Dela Cruz',
                'suffix': '',
                'birth_date': date(1985, 3, 15),
                'birth_place': 'Maasin City, Southern Leyte',
                'blood_type': 'O+',
                'mobile_number': '09171234567',
                'email': 'juan.delacruz@example.com',
                'house_number': '123',
                'street': 'Rizal Street',
                'barangay': 'Abgao',
                'zip_code': '6600',
                'city_municipality': 'Maasin City',
                'province': 'Southern Leyte',
                'license_number': 'N01-85-123456',
                'license_expiry': future_expiry,
                'emergency_contact_name': 'Maria Dela Cruz',
                'emergency_contact_number': '09181234567',
                'emergency_contact_relationship': 'Spouse',
            },
            {
                'first_name': 'Pedro',
                'middle_name': 'Garcia',
                'last_name': 'Reyes',
                'suffix': 'Jr.',
                'birth_date': date(1990, 7, 22),
                'birth_place': 'Sogod, Southern Leyte',
                'blood_type': 'A+',
                'mobile_number': '09182345678',
                'email': 'pedro.reyes@example.com',
                'house_number': '456',
                'street': 'Bonifacio Avenue',
                'barangay': 'Guadalupe',
                'zip_code': '6600',
                'city_municipality': 'Maasin City',
                'province': 'Southern Leyte',
                'license_number': 'N01-90-234567',
                'license_expiry': future_expiry,
                'emergency_contact_name': 'Rosa Reyes',
                'emergency_contact_number': '09192345678',
                'emergency_contact_relationship': 'Mother',
            },
            {
                'first_name': 'Carlos',
                'middle_name': 'Mendoza',
                'last_name': 'Santos',
                'suffix': '',
                'birth_date': date(1988, 11, 8),
                'birth_place': 'Bato, Southern Leyte',
                'blood_type': 'B+',
                'mobile_number': '09193456789',
                'email': 'carlos.santos@example.com',
                'house_number': '789',
                'street': 'Mabini Street',
                'barangay': 'Tunga-tunga',
                'zip_code': '6600',
                'city_municipality': 'Maasin City',
                'province': 'Southern Leyte',
                'license_number': 'N01-88-345678',
                'license_expiry': future_expiry,
                'emergency_contact_name': 'Ana Santos',
                'emergency_contact_number': '09203456789',
                'emergency_contact_relationship': 'Sister',
            },
        ]

        drivers = []
        for idx, driver_data in enumerate(drivers_data, 1):
            # Create a simple placeholder image for driver photo
            driver_photo_file = self._create_placeholder_image(f'Driver {idx}')
            
            # Create driver
            driver = Driver(**driver_data)
            driver.driver_photo.save(
                f'driver_{idx}_photo.png',
                driver_photo_file,
                save=False
            )
            driver.save()
            
            drivers.append(driver)
            self.stdout.write(f'  ✓ Created driver: {driver.first_name} {driver.last_name} (ID: {driver.driver_id})')

        return drivers

    def _create_vehicles(self, drivers, routes):
        """Create 3 vehicles, each assigned to one driver (1:1 relationship)."""
        # Future date for registration expiry (2 years from now)
        future_expiry = date.today() + timedelta(days=730)
        current_year = timezone.now().year

        vehicles_data = [
            {
                'vehicle_name': 'Lucky Star Jeepney',
                'vehicle_type': 'jeepney',
                'ownership_type': 'owned',
                'cr_number': 'CR-2024-001234',
                'or_number': 'OR-2024-001234',
                'vin_number': 'JH4KA7532MC000001',  # Valid VIN format
                'year_model': current_year - 2,  # 2 years old
                'registration_number': 'REG-2024-001234',
                'registration_expiry': future_expiry,
                'license_plate': 'ABC-1234',
                'seat_capacity': 25,
                'status': 'idle',
            },
            {
                'vehicle_name': 'Swift Van Express',
                'vehicle_type': 'van',
                'ownership_type': 'leased',
                'cr_number': 'CR-2024-002345',
                'or_number': 'OR-2024-002345',
                'vin_number': 'JH4KA7532MC000002',  # Valid VIN format
                'year_model': current_year - 1,  # 1 year old
                'registration_number': 'REG-2024-002345',
                'registration_expiry': future_expiry,
                'license_plate': 'XYZ-5678',
                'seat_capacity': 15,
                'status': 'idle',
            },
            {
                'vehicle_name': 'Comfort Bus Line',
                'vehicle_type': 'bus',
                'ownership_type': 'owned',
                'cr_number': 'CR-2024-003456',
                'or_number': 'OR-2024-003456',
                'vin_number': 'JH4KA7532MC000003',  # Valid VIN format
                'year_model': current_year - 3,  # 3 years old
                'registration_number': 'REG-2024-003456',
                'registration_expiry': future_expiry,
                'license_plate': 'DEF-9012',
                'seat_capacity': 60,
                'status': 'idle',
            },
        ]

        vehicles = []
        for idx, vehicle_data in enumerate(vehicles_data):
            # Assign driver (1:1 relationship)
            driver = drivers[idx]
            
            # Assign route (cycling through available routes)
            route = routes[idx % len(routes)]

            # Create vehicle - QR code will be auto-generated by save method
            vehicle = Vehicle.objects.create(
                **vehicle_data,
                assigned_driver=driver,
                route=route
            )
            
            vehicles.append(vehicle)
            self.stdout.write(
                f'  ✓ Created vehicle: {vehicle.vehicle_name} ({vehicle.license_plate}) '
                f'→ Driver: {driver.first_name} {driver.last_name}'
            )

        return vehicles

    def _create_placeholder_image(self, text):
        """Create a simple placeholder image for driver photo."""
        # Create a simple 200x200 image with text
        img = Image.new('RGB', (200, 200), color=(73, 109, 137))
        
        # Save to BytesIO
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Return as ContentFile
        return ContentFile(buffer.read(), name=f'{text.replace(" ", "_").lower()}.png')

    def _display_results(self, drivers, vehicles):
        """Display the created data in a formatted table."""
        self.stdout.write('\n📊 CREATED DATA SUMMARY:')
        self.stdout.write('=' * 70)

        # Display Drivers
        self.stdout.write(self.style.SUCCESS('\n👤 DRIVERS:'))
        self.stdout.write('-' * 70)
        for driver in drivers:
            self.stdout.write(f'  ID: {driver.driver_id}')
            self.stdout.write(f'  Name: {driver.first_name} {driver.last_name}')
            self.stdout.write(f'  License: {driver.license_number}')
            self.stdout.write(f'  License Expiry: {driver.license_expiry}')
            self.stdout.write(f'  Mobile: {driver.mobile_number}')
            self.stdout.write('-' * 70)

        # Display Vehicles
        self.stdout.write(self.style.SUCCESS('\n🚗 VEHICLES:'))
        self.stdout.write('-' * 70)
        for vehicle in vehicles:
            self.stdout.write(f'  Name: {vehicle.vehicle_name}')
            self.stdout.write(f'  Plate: {vehicle.license_plate}')
            self.stdout.write(f'  Type: {vehicle.get_vehicle_type_display()}')
            self.stdout.write(f'  Registration: {vehicle.registration_number}')
            self.stdout.write(f'  Registration Expiry: {vehicle.registration_expiry}')
            self.stdout.write(f'  Driver: {vehicle.assigned_driver.first_name} {vehicle.assigned_driver.last_name}')
            self.stdout.write(f'  Route: {vehicle.route}')
            self.stdout.write(f'  QR Code: {vehicle.qr_value}')
            self.stdout.write('-' * 70)

        # Display Relationship Mapping
        self.stdout.write(self.style.SUCCESS('\n🔗 DRIVER → VEHICLE MAPPING:'))
        self.stdout.write('-' * 70)
        for idx, (driver, vehicle) in enumerate(zip(drivers, vehicles), 1):
            self.stdout.write(
                f'  {idx}. {driver.first_name} {driver.last_name} ({driver.driver_id}) '
                f'→ {vehicle.vehicle_name} ({vehicle.license_plate})'
            )
        self.stdout.write('-' * 70)

        # Display Wallets
        self.stdout.write(self.style.SUCCESS('\n💰 WALLETS (Auto-created):'))
        self.stdout.write('-' * 70)
        for vehicle in vehicles:
            wallet = vehicle.wallet
            self.stdout.write(
                f'  {vehicle.license_plate}: ₱{wallet.balance} '
                f'(Driver: {vehicle.assigned_driver.first_name} {vehicle.assigned_driver.last_name})'
            )
        self.stdout.write('-' * 70)

        self.stdout.write(self.style.SUCCESS('\n✅ All mock data created successfully!'))
        self.stdout.write(self.style.WARNING('\n💡 TIP: Use --clear flag to remove existing data before creating new data'))
        self.stdout.write(self.style.WARNING('   Example: python manage.py create_mock_data --clear\n'))
