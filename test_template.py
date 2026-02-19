import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rdfs.settings')
django.setup()

from django.template import Template, Context
from django.template.loader import get_template
from django.http import HttpRequest

# Create a mock request
request = HttpRequest()
request.GET = {'modal': '1'}
request.user = type('User', (), {'is_authenticated': True, 'role': 'treasurer'})()

try:
    template = get_template('terminal/treasurer_request_deposit.html')
    print("✓ Template loaded successfully")
    
    # Try to render with minimal context
    context = {
        'request': request,
        'min_deposit_amount': 100.00,
    }
    
    html = template.render(context)
    print("✓ Template rendered successfully")
    print(f"✓ Output length: {len(html)} characters")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
