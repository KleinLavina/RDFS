"""
Management command to reset and create fresh mock data for drivers and vehicles.
Usage: python manage.py reset_mock_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from vehicles.models import Driver, Vehicle, Route, Wallet
from datetime import date, timedelta
from decimal import Decimal
import os
from django.conf import settings


class Command(BaseCommand):
    help = 'Clear all drivers and vehicles, then create 3 mock drivers and 3 mock vehicles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-routes',
            action='store_true',
            help='Keep existing routes instead of creating new ones',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🗑️  Starting data reset...'))
        
        with transaction.atomic():
            # Step 1: Delete all vehicles and drivers (cascades to wallets, etc.)
            vehicle_count = Vehicle.objects.count()
            driver_count = Driver.objects.count()
            
            self.stdout.write(f'Deleting {vehicle_count} vehicles...')
            Vehicle.objects.all().delete()
            
            self.stdout.write(f'Deleting {driver_count} drivers...')
            Driver.objects.all().delete()
            
            self.stdout.write(self.style.SUCCESS('✅ All vehicles and drivers deleted'))
            
            # Step 2: Create or get routes
            if not options['keep_routes']:
                Route.objects.all().delete()
                self.stdout.write('Creating fresh routes...')
            
            route1, _ = Route.objects.get_or_create(
                origin='Maasin City',
                destination='Sogod',
                defaults={
                    'name': 'Maasin-Sogod Route',
                    'base_fare': Decimal('50.00'),
                    'active': True
                }
            )
            
            route2, _ = Route.objects.get_or_create(
                origin='Maasin City',
                destination='Bato',
                defaults={
                    'name': 'Maasin-Bato Route',
                    'base_fare': Decimal('45.00'),
                    'active': True
                }
            )
            
            route3, _ = Route.objects.get_or_create(
                origin='Maasin City',
                destination='Hinunangan',
                defaults={
                    'name': 'Maasin-Hinunangan Route',
                    'base_fare': Decimal('60.00'),
                    'active': True
                }
            )
            
            self.stdout.write(self.style.SUCCESS(f'✅ Routes ready: {Route.objects.count()} routes'))
            
            # Step 3: Create 3 mock drivers
            self.stdout.write('Creating 3 mock drivers...')
            
            # Set expiry dates to 2 years in the future
            future_expiry = date.today() + timedelta(days=730)
            
            # Note: Skipping driver_photo for now since CloudinaryField requires special handling
            # In production with Cloudinary, photos would be uploaded properly
            
            driver1 = Driver(
                first_name='Juan',
                last_name='Dela Cruz',
                license_number='N01-12-345678',
                license_expiry=future_expiry,
                mobile_number='09171234567',
                city_municipality='Maasin City',
                province='Southern Leyte',
                driver_photo='placeholder/driver1.jpg'  # Placeholder path
            )
            driver1.save()
            
            driver2 = Driver(
                first_name='Maria',
                last_name='Santos',
                license_number='N01-12-876543',
                license_expiry=future_expiry,
                mobile_number='09181234567',
                city_municipality='Sogod',
                province='Southern Leyte',
                driver_photo='placeholder/driver2.jpg'  # Placeholder path
            )
            driver2.save()
            
            driver3 = Driver(
                first_name='Pedro',
                last_name='Reyes',
                license_number='N01-12-456789',
                license_expiry=future_expiry,
                mobile_number='09191234567',
                city_municipality='Bato',
                province='Southern Leyte',
                driver_photo='placeholder/driver3.jpg'  # Placeholder path
            )
            driver3.save()
            
            self.stdout.write(self.style.SUCCESS(f'✅ Created 3 drivers (with placeholder photos)'))
            
            # Step 4: Create 3 mock vehicles (1:1 with drivers)
            self.stdout.write('Creating 3 mock vehicles...')
            
            from datetime import datetime
            current_year = datetime.now().year
            
            vehicle1 = Vehicle.objects.create(
                vehicle_name='Jeepney 1',
                license_plate='ABC-1234',
                vehicle_type='jeepney',
                ownership_type='owned',
                assigned_driver=driver1,
                route=route1,
                qr_value='QR-ABC-1234',
                registration_number='REG-ABC-1234',
                registration_expiry=future_expiry,
                cr_number='CR-ABC-1234',
                or_number='OR-ABC-1234',
                vin_number='1HGBH41JXMN109186',
                year_model=current_year - 5,
                seat_capacity=16
            )
            
            vehicle2 = Vehicle.objects.create(
                vehicle_name='Van 1',
                license_plate='XYZ-5678',
                vehicle_type='van',
                ownership_type='owned',
                assigned_driver=driver2,
                route=route2,
                qr_value='QR-XYZ-5678',
                registration_number='REG-XYZ-5678',
                registration_expiry=future_expiry,
                cr_number='CR-XYZ-5678',
                or_number='OR-XYZ-5678',
                vin_number='2HGBH41JXMN109187',
                year_model=current_year - 3,
                seat_capacity=15
            )
            
            vehicle3 = Vehicle.objects.create(
                vehicle_name='Jeepney 2',
                license_plate='DEF-9012',
                vehicle_type='jeepney',
                ownership_type='owned',
                assigned_driver=driver3,
                route=route3,
                qr_value='QR-DEF-9012',
                registration_number='REG-DEF-9012',
                registration_expiry=future_expiry,
                cr_number='CR-DEF-9012',
                or_number='OR-DEF-9012',
                vin_number='3HGBH41JXMN109188',
                year_model=current_year - 4,
                seat_capacity=20
            )
            
            self.stdout.write(self.style.SUCCESS(f'✅ Created 3 vehicles'))
            
            # Step 5: Create wallets with initial balance
            self.stdout.write('Creating wallets with initial balance...')
            
            for vehicle in [vehicle1, vehicle2, vehicle3]:
                wallet, created = Wallet.objects.get_or_create(vehicle=vehicle)
                wallet.balance = Decimal('500.00')
                wallet.save()
            
            self.stdout.write(self.style.SUCCESS(f'✅ Wallets updated with ₱500.00 initial balance'))
            
            # Refresh vehicle data to get updated wallet balances
            vehicle1.refresh_from_db()
            vehicle2.refresh_from_db()
            vehicle3.refresh_from_db()
            
            # Summary
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('🎉 MOCK DATA CREATION COMPLETE!'))
            self.stdout.write('='*60)
            self.stdout.write(f'\n📊 Summary:')
            self.stdout.write(f'   • Routes: {Route.objects.count()}')
            self.stdout.write(f'   • Drivers: {Driver.objects.count()}')
            self.stdout.write(f'   • Vehicles: {Vehicle.objects.count()}')
            self.stdout.write(f'   • Wallets: {Wallet.objects.count()}')
            
            self.stdout.write(f'\n🚗 Vehicles Created:')
            for v in Vehicle.objects.all():
                self.stdout.write(f'   • {v.license_plate} - {v.vehicle_type.upper()} - Driver: {v.assigned_driver.first_name} {v.assigned_driver.last_name}')
                self.stdout.write(f'     Route: {v.route.origin} → {v.route.destination}')
                self.stdout.write(f'     QR Code: {v.qr_value}')
                self.stdout.write(f'     Wallet Balance: ₱{v.wallet.balance}')
            
            self.stdout.write(f'\n✅ All expiry dates set to: {future_expiry.strftime("%B %d, %Y")}')
            self.stdout.write(f'✅ Strict 1:1 driver-vehicle relationship maintained')
            self.stdout.write('\n' + '='*60 + '\n')
