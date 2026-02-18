"""
Management command to regenerate QR codes for all vehicles.
Usage: python manage.py regenerate_qr_codes
"""
import qrcode
from io import BytesIO
from django.core.management.base import BaseCommand
from vehicles.models import Vehicle
import cloudinary.uploader


class Command(BaseCommand):
    help = 'Regenerate QR codes for all vehicles'

    def handle(self, *args, **options):
        vehicles = Vehicle.objects.all()
        
        if not vehicles.exists():
            self.stdout.write(self.style.WARNING('No vehicles found in database.'))
            return
        
        self.stdout.write(f'Found {vehicles.count()} vehicle(s). Regenerating QR codes...\n')
        
        success_count = 0
        error_count = 0
        
        for vehicle in vehicles:
            try:
                # Generate QR value
                qr_value = f"VEH-{vehicle.id}-{vehicle.license_plate}".replace(" ", "-").upper()
                vehicle.qr_value = qr_value
                
                # Generate QR code image
                qr_img = qrcode.make(qr_value)
                buffer = BytesIO()
                qr_img.save(buffer, format="PNG")
                buffer.seek(0)
                
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(
                    buffer,
                    folder="vehicles/qrcodes",
                    public_id=f"vehicle_{vehicle.id}_qr",
                    overwrite=True,
                    resource_type="image"
                )
                vehicle.qr_code = upload_result['secure_url']
                vehicle.save(update_fields=["qr_code", "qr_value"])
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ {vehicle.license_plate} - QR: {qr_value}'
                    )
                )
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Failed for {vehicle.license_plate}: {str(e)}'
                    )
                )
                error_count += 1
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ Successfully regenerated: {success_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ Failed: {error_count}'))
        self.stdout.write('='*60)
