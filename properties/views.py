from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView, UpdateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.db.models import Q, Min, Max
from django.contrib import messages
from .models import Property, PropertyImage, SharedPropertyList, UserProfile
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import login
from .forms import PropertyQuickAddForm, PropertyForm, PropertyConfigurationFormSet, PropertyImageFormSet, CustomUserCreationForm
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def landing_view(request):
    """Landing page with card-style property display"""
    # Check if user is authenticated and is an employee
    is_employee = False
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            is_employee = profile.is_employee
        except UserProfile.DoesNotExist:
            pass
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    min_bedrooms = request.GET.get('min_bedrooms')
    max_bedrooms = request.GET.get('max_bedrooms')
    min_bathrooms = request.GET.get('min_bathrooms')
    max_bathrooms = request.GET.get('max_bathrooms')
    luxury_status = request.GET.get('luxury_status')
    
    # Base queryset - only show active properties
    properties = Property.objects.filter(is_active=True).prefetch_related(
        'configurations', 'images', 'amenities'
    )
    
    # If not employee, only show properties that are in active shared lists or all if no shared lists exist
    if not is_employee:
        # This will be handled by shared link view instead
        properties = properties.none()
    
    # Apply filters
    if search_query:
        properties = properties.filter(
            Q(name__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if luxury_status:
        properties = properties.filter(luxury_status=luxury_status)
    
    # Filter by price range
    if min_price:
        properties = properties.filter(configurations__price__gte=min_price).distinct()
    if max_price:
        properties = properties.filter(configurations__price__lte=max_price).distinct()
    
    # Filter by bedrooms
    if min_bedrooms:
        properties = properties.filter(configurations__bedrooms__gte=min_bedrooms).distinct()
    if max_bedrooms:
        properties = properties.filter(configurations__bedrooms__lte=max_bedrooms).distinct()
    
    # Filter by bathrooms
    if min_bathrooms:
        properties = properties.filter(configurations__bathrooms__gte=min_bathrooms).distinct()
    if max_bathrooms:
        properties = properties.filter(configurations__bathrooms__lte=max_bathrooms).distinct()
    
    # Get filter ranges for the filter form
    all_properties = Property.objects.filter(is_active=True)
    price_range = all_properties.aggregate(
        min_price=Min('configurations__price'),
        max_price=Max('configurations__price')
    )
    bedroom_range = all_properties.aggregate(
        min_bedrooms=Min('configurations__bedrooms'),
        max_bedrooms=Max('configurations__bedrooms')
    )
    bathroom_range = all_properties.aggregate(
        min_bathrooms=Min('configurations__bathrooms'),
        max_bathrooms=Max('configurations__bathrooms')
    )
    
    context = {
        'properties': properties,
        'is_employee': is_employee,
        'search_query': search_query,
        'filters': {
            'min_price': min_price,
            'max_price': max_price,
            'min_bedrooms': min_bedrooms,
            'max_bedrooms': max_bedrooms,
            'min_bathrooms': min_bathrooms,
            'max_bathrooms': max_bathrooms,
            'luxury_status': luxury_status,
        },
        'filter_ranges': {
            'price_range': price_range,
            'bedroom_range': bedroom_range,
            'bathroom_range': bathroom_range,
        }
    }
    
    return render(request, 'landing.html', context)

def dashboard_view(request):
    """Map dashboard view - for employees only"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        profile = request.user.profile
        if not profile.is_employee:
            messages.error(request, 'Access denied. Employee access required.')
            return redirect('landing')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied. Employee access required.')
        return redirect('landing')
    
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

def property_detail_api(request, property_id):
    """API endpoint to get a single property's details as JSON"""
    property = get_object_or_404(Property.objects.prefetch_related(
        'configurations', 'images', 'amenities'
    ), id=property_id, is_active=True)

    images = [request.build_absolute_uri(img.image.url) for img in property.images.all()]
    thumbnail = request.build_absolute_uri(property.thumbnail.url) if property.thumbnail else None
    configurations = [
        {
            'type': config.type,
            'bedrooms': config.bedrooms,
            'bathrooms': config.bathrooms,
            'square_footage': config.square_footage,
            'price': f"₦{float(config.price):,.2f}" if config.price is not None else "TBD"
        }
        for config in property.configurations.all()
    ]
    amenities = [amenity.name for amenity in property.amenities.all()]

    property_data = {
        'id': property.id,
        'name': property.name,
        'latitude': float(property.latitude),
        'longitude': float(property.longitude),
        'address': property.address,
        'description': property.description,
        'configurations': configurations,
        'amenities': amenities,
        'thumbnail': thumbnail,
        'images': images,
        'contact': f"{property.contact_name} - {property.contact_phone}",
        'brochure': request.build_absolute_uri(property.brochure.url) if property.brochure else "",
        'luxury_status': property.get_luxury_status_display()
    }

    return JsonResponse(property_data)
@login_required
def create_shared_list(request):
    """Create a shared property list with temporary link"""
    try:
        profile = request.user.profile
        if not profile.can_share_properties:
            return JsonResponse({'error': 'Permission denied'}, status=403)
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', 'Shared Properties')
        property_ids = data.get('property_ids', [])
        duration_hours = int(data.get('duration_hours', 72))  # Default 3 days
        
        if not property_ids:
            return JsonResponse({'error': 'No properties selected'}, status=400)
        
        # Create shared list
        expires_at = timezone.now() + timedelta(hours=duration_hours)
        shared_list = SharedPropertyList.objects.create(
            name=name,
            created_by=request.user,
            expires_at=expires_at
        )
        
        # Add properties
        properties = Property.objects.filter(id__in=property_ids, is_active=True)
        shared_list.properties.set(properties)
        
        # Generate shareable URL
        share_url = request.build_absolute_uri(f'/shared/{shared_list.token}/')
        
        return JsonResponse({
            'success': True,
            'share_url': share_url,
            'token': shared_list.token,
            'expires_at': shared_list.expires_at.isoformat(),
            'property_count': properties.count()
        })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def shared_properties_view(request, token):
    """View shared properties via temporary link"""
    shared_list = get_object_or_404(SharedPropertyList, token=token)
    
    # if not shared_list.is_valid or shared_list.is_expired or not shared_list.is_active:
    #     return render(request, 'shared_expired.html', {'shared_list': shared_list})
    
    if not shared_list.is_valid():
        if shared_list.is_expired or shared_list.is_active:
            return render(request, 'shared_expired.html', {'shared_list': shared_list})
        else:
            raise Http404("Shared list not found or inactive")
    
    # Increment view count
    shared_list.view_count += 1
    shared_list.save(update_fields=['view_count'])
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    min_bedrooms = request.GET.get('min_bedrooms')
    max_bedrooms = request.GET.get('max_bedrooms')
    min_bathrooms = request.GET.get('min_bathrooms')
    max_bathrooms = request.GET.get('max_bathrooms')
    luxury_status = request.GET.get('luxury_status')
    
    # Get properties from shared list
    properties = shared_list.properties.filter(is_active=True).prefetch_related(
        'configurations', 'images', 'amenities'
    )
    
    # Apply filters
    if search_query:
        properties = properties.filter(
            Q(name__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if luxury_status:
        properties = properties.filter(luxury_status=luxury_status)
    
    # Filter by price range
    if min_price:
        properties = properties.filter(configurations__price__gte=min_price).distinct()
    if max_price:
        properties = properties.filter(configurations__price__lte=max_price).distinct()
    
    # Filter by bedrooms
    if min_bedrooms:
        properties = properties.filter(configurations__bedrooms__gte=min_bedrooms).distinct()
    if max_bedrooms:
        properties = properties.filter(configurations__bedrooms__lte=max_bedrooms).distinct()
    
    # Filter by bathrooms
    if min_bathrooms:
        properties = properties.filter(configurations__bathrooms__gte=min_bathrooms).distinct()
    if max_bathrooms:
        properties = properties.filter(configurations__bathrooms__lte=max_bathrooms).distinct()
    
    # Get filter ranges
    all_shared_properties = shared_list.properties.filter(is_active=True)
    price_range = all_shared_properties.aggregate(
        min_price=Min('configurations__price'),
        max_price=Max('configurations__price')
    )
    bedroom_range = all_shared_properties.aggregate(
        min_bedrooms=Min('configurations__bedrooms'),
        max_bedrooms=Max('configurations__bedrooms')
    )
    bathroom_range = all_shared_properties.aggregate(
        min_bathrooms=Min('configurations__bathrooms'),
        max_bathrooms=Max('configurations__bathrooms')
    )
    
    context = {
        'properties': properties,
        'shared_list': shared_list,
        'is_shared_view': True,
        'search_query': search_query,
        'filters': {
            'min_price': min_price,
            'max_price': max_price,
            'min_bedrooms': min_bedrooms,
            'max_bedrooms': max_bedrooms,
            'min_bathrooms': min_bathrooms,
            'max_bathrooms': max_bathrooms,
            'luxury_status': luxury_status,
        },
        'filter_ranges': {
            'price_range': price_range,
            'bedroom_range': bedroom_range,
            'bathroom_range': bathroom_range,
        }
    }
    
    return render(request, 'shared_properties.html', context)

@login_required
def manage_shared_lists(request):
    """Manage shared property lists"""
    try:
        profile = request.user.profile
        if not profile.can_share_properties:
            messages.error(request, 'Permission denied.')
            return redirect('landing')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Permission denied.')
        return redirect('landing')
    
    shared_lists = SharedPropertyList.objects.filter(created_by=request.user)
    
    return render(request, 'manage_shared_lists.html', {
        'shared_lists': shared_lists
    })
    
@login_required
def delete_shared_list(request, list_id):
    if request.method == 'POST':
        try:
            shared_list = SharedPropertyList.objects.get(id=list_id, created_by=request.user)
            shared_list.delete()
            logger.info(f"Deleted shared list {list_id} by user {request.user}")
            return JsonResponse({'status': 'success'})
        except SharedPropertyList.DoesNotExist:
            logger.error(f"Shared list {list_id} not found for user {request.user}")
            return JsonResponse({'status': 'error', 'message': 'Shared list not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting shared list {list_id}: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
        
@login_required
def toggle_shared_link(request, list_id):
    if request.method == 'POST':
        try:
            shared_list = SharedPropertyList.objects.get(id=list_id, created_by=request.user)
            data = json.loads(request.body)
            shared_list.is_active = data.get('active', shared_list.is_active)
            shared_list.save()
            return JsonResponse({'status': 'success', 'active': shared_list.is_active})
        except SharedPropertyList.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Shared list not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)        
    
def register_view(request):
    """User registration"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('landing')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'register.html', {'form': form})

@staff_member_required
def create_employee_view(request):
    """Admin view to create employee users"""
    if request.method == 'POST':
        from .forms import EmployeeUserCreationForm
        form = EmployeeUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Employee account created successfully for {user.get_full_name() or user.username}!')
            return redirect('login')
    else:
        from .forms import EmployeeUserCreationForm
        form = EmployeeUserCreationForm()
    
    return render(request, 'create_employee.html', {'form': form})