"""
Django management command to create mock deposit data for previous months.
Usage: python manage.py create_mock_deposits
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from vehicles.models import Wallet, Deposit
from terminal.models import SystemSettings


User = get_user_model()


class Command(BaseCommand):
    help = 'Create mock deposit data for January 2026 and December 2025'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing mock deposits before creating new ones',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('CREATING MOCK DEPOSIT DATA'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))

        # Clear existing mock deposits if requested
        if options['clear']:
            self.stdout.write('Clearing existing deposits...')
            Deposit.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ All deposits cleared\n'))

        # Get system settings for minimum deposit
        try:
            settings = SystemSettings.objects.first()
            min_deposit = settings.min_deposit_amount if settings else Decimal('100.00')
        except Exception:
            min_deposit = Decimal('100.00')

        self.stdout.write(f'Minimum deposit amount: ₱{min_deposit}\n')

        # Get or create admin user
        admin_user = self._get_or_create_admin()
        
        # Get all existing wallets
        wallets = list(Wallet.objects.select_related('vehicle__assigned_driver').all())
        
        if not wallets:
            self.stdout.write(self.style.ERROR('✗ No wallets found. Please create vehicles first.'))
            return

        self.stdout.write(f'Found {len(wallets)} wallet(s)\n')

        # Define months to generate data for
        months_to_generate = [
            {'year': 2026, 'month': 1, 'name': 'January 2026'},
            {'year': 2025, 'month': 12, 'name': 'December 2025'},
        ]

        total_created = 0

        for month_data in months_to_generate:
            self.stdout.write(f'\nGenerating deposits for {month_data["name"]}...')
            
            created_count = self._create_deposits_for_month(
                year=month_data['year'],
                month=month_data['month'],
                wallets=wallets,
                admin_user=admin_user,
                min_deposit=min_deposit,
                count=10
            )
            
            total_created += created_count
            self.stdout.write(self.style.SUCCESS(f'✓ Created {created_count} deposits for {month_data["name"]}'))

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS(f'TOTAL DEPOSITS CREATED: {total_created}'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

    def _get_or_create_admin(self):
        """Get or create an admin user for created_by field."""
        admin_user = User.objects.filter(role='admin').first()
        
        if not admin_user:
            self.stdout.write(self.style.WARNING('No admin user found. Creating one...'))
            admin_user = User.objects.create_user(
                username='mock_admin',
                email='mock_admin@example.com',
                password='password123',
                role='admin',
                first_name='Mock',
                last_name='Admin'
            )
            self.stdout.write(self.style.SUCCESS('✓ Created mock admin user'))
        else:
            self.stdout.write(f'Using admin user: {admin_user.username}')
        
        return admin_user

    def _create_deposits_for_month(self, year, month, wallets, admin_user, min_deposit, count=10):
        """Create deposits for a specific month."""
        created_count = 0
        
        # Get the first and last day of the month
        first_day = datetime(year, month, 1)
        
        # Calculate last day of month
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)

        # Generate deposits
        for i in range(count):
            # Random date within the month
            random_day = random.randint(1, last_day.day)
            random_hour = random.randint(8, 17)  # Business hours
            random_minute = random.randint(0, 59)
            
            deposit_date = timezone.make_aware(
                datetime(year, month, random_day, random_hour, random_minute)
            )
            
            # Random wallet
            wallet = random.choice(wallets)
            
            # Random amount (between min_deposit and min_deposit * 5)
            amount = Decimal(random.randint(int(min_deposit), int(min_deposit * 5)))
            
            # Random payment method
            payment_method = random.choice(['cash', 'gcash', 'bank_transfer'])
            
            try:
                with transaction.atomic():
                    # Create deposit without triggering auto_now_add
                    deposit = Deposit(
                        wallet=wallet,
                        amount=amount,
                        created_by=admin_user,
                        status='successful',
                        payment_method=payment_method,
                    )
                    
                    # Save without triggering wallet balance update
                    # We'll manually set created_at
                    deposit.save()
                    
                    # Update created_at to the random date
                    Deposit.objects.filter(pk=deposit.pk).update(
                        created_at=deposit_date,
                        updated_at=deposit_date
                    )
                    
                    created_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error creating deposit: {e}'))
                continue

        return created_count
