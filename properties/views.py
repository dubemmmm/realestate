from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import CreateView, UpdateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Property, PropertyImage
from .forms import PropertyQuickAddForm, PropertyForm, PropertyConfigurationFormSet, PropertyImageFormSet

def dashboard_view(request):
    """Main dashboard view"""
    return render(request, 'dashboard.html')

def properties_api(request):
    """API endpoint to get all properties as JSON for the map"""
    properties = Property.objects.filter(is_active=True).prefetch_related(
        'configurations', 'images', 'amenities'
    )
    
    properties_data = []
    for prop in properties:
        images = [request.build_absolute_uri(img.image.url) for img in prop.images.all()]
        thumbnail = request.build_absolute_uri(prop.thumbnail.url) if prop.thumbnail else None
        configurations = [
            {
                'type': config.type,
                'bedrooms': config.bedrooms,
                'bathrooms': config.bathrooms,
                'square_footage': config.square_footage,
                'price': f"₦{float(config.price):,.2f}" if config.price is not None else "TBD"
            }
            for config in prop.configurations.all()
        ]
        amenities = [amenity.name for amenity in prop.amenities.all()]
        properties_data.append({
            'id': prop.id,
            'name': prop.name,
            'latitude': float(prop.latitude),
            'longitude': float(prop.longitude),
            'address': prop.address,
            'description': prop.description,
            'configurations': configurations,
            'amenities': amenities,
            'thumbnail': thumbnail,
            'images': images,
            'contact': f"{prop.contact_name} - {prop.contact_phone}",
            'brochure': request.build_absolute_uri(prop.brochure.url) if prop.brochure else "",
            'luxury_status': prop.get_luxury_status_display()
        })
    
    return JsonResponse(properties_data, safe=False)
