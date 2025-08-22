from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView, UpdateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.db.models import Q, Min, Max
from django.contrib import messages
from .models import SharedPropertyList, UserProfile, Property, PropertyConfiguration, PropertyImage, PropertyAmenity
from django.utils import timezone
from django.db.models.functions import ExtractMonth, ExtractYear
from datetime import timedelta
from django.contrib.auth import login
from datetime import datetime, timedelta
from decouple import config
from .forms import CustomUserCreationForm
import json
import logging
from django.urls import reverse, reverse_lazy
from io import BytesIO
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.conf import settings
from django.core.files.storage import default_storage
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from PIL import Image as PILImage
from calendar import month_name
import os
import requests
from decimal import Decimal
import requests
logger = logging.getLogger(__name__)

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from decimal import Decimal, InvalidOperation
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)



def get_property_min_price(configurations):
    """
    Get the minimum price from property configurations
    """
    if not configurations:
        return None
    
    prices = []
    for config in configurations:
        if config.get('price') and config.get('is_available', True):
            try:
                # Handle Decimal objects
                if isinstance(config['price'], Decimal):
                    prices.append(float(config['price']))
                elif isinstance(config['price'], (int, float)):
                    prices.append(float(config['price']))
                elif isinstance(config['price'], str):
                    # Try to convert string to float, removing any currency symbols
                    clean_price = config['price'].replace('₦', '').replace(',', '').strip()
                    if clean_price and clean_price.replace('.', '').isdigit():
                        prices.append(float(clean_price))
            except (ValueError, TypeError):
                continue
    
    return min(prices) if prices else None

def apply_search_filter(properties, search_query):
    """
    Apply search filter to properties
    """
    if not search_query:
        return properties
    
    search_query = search_query.lower()
    filtered_properties = []
    
    for prop in properties:
        # Search in name, address, and description
        searchable_text = ' '.join([
            prop.get('name', '').lower(),
            prop.get('address', '').lower(),
            prop.get('description', '').lower()
        ])
        
        if search_query in searchable_text:
            filtered_properties.append(prop)
    
    return filtered_properties

def apply_price_filter(properties, min_price, max_price):
    """
    Apply price range filter to properties
    """
    filtered_properties = []
    
    for prop in properties:
        prop_prices = []
        
        # Get all prices from configurations
        for config in prop.get('configurations', []):
            if config.get('price') and config.get('is_available', True):
                try:
                    if isinstance(config['price'], Decimal):
                        prop_prices.append(float(config['price']))
                    elif isinstance(config['price'], (int, float)):
                        prop_prices.append(float(config['price']))
                    elif isinstance(config['price'], str):
                        clean_price = config['price'].replace('₦', '').replace(',', '').strip()
                        if clean_price and clean_price.replace('.', '').isdigit():
                            prop_prices.append(float(clean_price))
                except (ValueError, TypeError):
                    continue
        
        if not prop_prices:
            # If no valid prices, include property only if no price filter is applied
            if not min_price and not max_price:
                filtered_properties.append(prop)
            continue
        
        # Check if any price falls within the range
        min_prop_price = min(prop_prices)
        max_prop_price = max(prop_prices)
        
        include_property = True
        
        if min_price:
            try:
                min_price_float = float(min_price)
                if max_prop_price < min_price_float:
                    include_property = False
            except (ValueError, TypeError):
                pass
        
        if max_price and include_property:
            try:
                max_price_float = float(max_price)
                if min_prop_price > max_price_float:
                    include_property = False
            except (ValueError, TypeError):
                pass
        
        if include_property:
            filtered_properties.append(prop)
    
    return filtered_properties

def apply_bedroom_bathroom_filter(properties, min_bedrooms, max_bedrooms, min_bathrooms, max_bathrooms):
    """
    Apply bedroom and bathroom filters to properties
    """
    filtered_properties = []
    
    for prop in properties:
        configurations = prop.get('configurations', [])
        
        if not configurations:
            # If no configurations, include property only if no bedroom/bathroom filter is applied
            if not any([min_bedrooms, max_bedrooms, min_bathrooms, max_bathrooms]):
                filtered_properties.append(prop)
            continue
        
        # Check if any configuration matches the criteria
        matches_criteria = False
        
        for config in configurations:
            if not config.get('is_available', True):
                continue
                
            bedrooms = config.get('bedrooms', 0)
            bathrooms = config.get('bathrooms', 0)
            
            bedroom_match = True
            bathroom_match = True
            
            # Check bedroom criteria
            if min_bedrooms:
                try:
                    if bedrooms < int(min_bedrooms):
                        bedroom_match = False
                except (ValueError, TypeError):
                    pass
            
            if max_bedrooms and bedroom_match:
                try:
                    if bedrooms > int(max_bedrooms):
                        bedroom_match = False
                except (ValueError, TypeError):
                    pass
            
            # Check bathroom criteria
            if min_bathrooms:
                try:
                    if bathrooms < int(min_bathrooms):
                        bathroom_match = False
                except (ValueError, TypeError):
                    pass
            
            if max_bathrooms and bathroom_match:
                try:
                    if bathrooms > int(max_bathrooms):
                        bathroom_match = False
                except (ValueError, TypeError):
                    pass
            
            if bedroom_match and bathroom_match:
                matches_criteria = True
                break
        
        if matches_criteria:
            filtered_properties.append(prop)
    
    return filtered_properties

def get_filter_ranges(properties):
    """
    Calculate filter ranges from the current properties data
    """
    all_prices = []
    all_bedrooms = []
    all_bathrooms = []
    
    for prop in properties:
        for config in prop.get('configurations', []):
            # Collect prices
            if config.get('price') and config.get('is_available', True):
                try:
                    if isinstance(config['price'], Decimal):
                        all_prices.append(float(config['price']))
                    elif isinstance(config['price'], (int, float)):
                        all_prices.append(float(config['price']))
                    elif isinstance(config['price'], str):
                        clean_price = config['price'].replace('₦', '').replace(',', '').strip()
                        if clean_price and clean_price.replace('.', '').isdigit():
                            all_prices.append(float(clean_price))
                except (ValueError, TypeError):
                    continue
            
            # Collect bedrooms and bathrooms
            if isinstance(config.get('bedrooms'), (int, str)):
                try:
                    all_bedrooms.append(int(config['bedrooms']))
                except (ValueError, TypeError):
                    pass
            
            if isinstance(config.get('bathrooms'), (int, str)):
                try:
                    all_bathrooms.append(int(config['bathrooms']))
                except (ValueError, TypeError):
                    pass
    
    return {
        'price_range': {
            'min_price': min(all_prices) if all_prices else None,
            'max_price': max(all_prices) if all_prices else None
        },
        'bedroom_range': {
            'min_bedrooms': min(all_bedrooms) if all_bedrooms else None,
            'max_bedrooms': max(all_bedrooms) if all_bedrooms else None
        },
        'bathroom_range': {
            'min_bathrooms': min(all_bathrooms) if all_bathrooms else None,
            'max_bathrooms': max(all_bathrooms) if all_bathrooms else None
        }
    }


@login_required
def sync_airtable(request):
    """Trigger Airtable sync for properties"""
    try:
        profile = request.user.profile
        if not profile.is_employee:
            logger.warning(f"User {request.user.username} attempted to sync Airtable without permission")
            return JsonResponse({'error': 'Permission denied'}, status=403)
    except UserProfile.DoesNotExist:
        logger.warning(f"User {request.user.username} has no UserProfile")
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            # Run the sync_airtable_to_models command
            call_command('sync_airtable')
            logger.info(f"User {request.user.username} successfully triggered Airtable sync")
            return JsonResponse({
                'success': True,
                'message': 'Airtable sync completed successfully'
            })
        except Exception as e:
            logger.error(f"Airtable sync failed: {str(e)}")
            return JsonResponse({'error': f'Sync failed: {str(e)}'}, status=500)
    
    logger.warning(f"Invalid request method: {request.method}")
    return JsonResponse({'error': 'Invalid request method'}, status=405)






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

@login_required
def create_shared_list(request):
    """Create a shared property list with temporary link"""
    try:
        profile = request.user.profile
        if not profile.can_share_properties:
            logger.warning(f"User {request.user.username} attempted to create shared list without permission")
            return JsonResponse({'error': 'Permission denied'}, status=403)
    except UserProfile.DoesNotExist:
        logger.warning(f"User {request.user.username} has no UserProfile")
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', 'Shared Properties').strip()
            property_ids = data.get('property_ids', [])
            duration_hours = int(data.get('duration_hours', 72))  # Default 3 days
            
            if not property_ids:
                logger.error("No property IDs provided in request")
                return JsonResponse({'error': 'No properties selected'}, status=400)
            
            # Get properties and their airtable_ids
            properties = Property.objects.filter(id__in=property_ids, is_active=True)
            if not properties.exists():
                logger.error(f"No valid properties found for IDs: {property_ids}")
                return JsonResponse({'error': 'No valid properties found'}, status=400)
            
            # Collect airtable_ids from properties
            airtable_ids = [prop.airtable_id for prop in properties if prop.airtable_id]
            
            # Create shared list
            expires_at = timezone.now() + timedelta(hours=duration_hours)
            shared_list = SharedPropertyList.objects.create(
                name=name,
                created_by=request.user,
                expires_at=expires_at,
                airtable_ids=airtable_ids
            )
            
            # Add properties to the ManyToManyField
            shared_list.properties.set(properties)
            
            # Generate shareable URL using reverse to ensure correct path
            try:
                share_path = reverse('shared_properties', kwargs={'token': shared_list.token})
                share_url = request.build_absolute_uri(share_path)
                print(f"Generated share URL: {share_url}")
                logger.info(f"Generated share URL: {share_url}")
            except Exception as e:
                logger.error(f"Failed to generate share URL: {str(e)}")
                return JsonResponse({'error': f'Failed to generate share URL: {str(e)}'}, status=500)
            
            logger.info(f"Created shared list {shared_list.token} with {properties.count()} properties")
            
            return JsonResponse({
                'success': True,
                'share_url': share_url,
                'token': shared_list.token,
                'expires_at': shared_list.expires_at.isoformat(),
                'property_count': properties.count()
            })
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON data in request")
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except ValueError as e:
            logger.error(f"Invalid input: {str(e)}")
            return JsonResponse({'error': f'Invalid input: {str(e)}'}, status=400)
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
    
    logger.warning(f"Invalid request method: {request.method}")
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
    completion_date = request.GET.get('completion_date')
    
    
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
    
    # Filter by completion date
    if completion_date:
        properties = properties.filter(completion_date__lte=completion_date)
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



def properties_api(request):
    """API endpoint to get all properties as JSON for the map"""
    properties = Property.objects.filter(is_active=True).prefetch_related(
        'configurations', 'images', 'amenities'
    )
    print(properties)
    
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
            'luxury_status': prop.get_luxury_status_display(),
            'completion_date': prop.completion_date
            
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
        'luxury_status': property.get_luxury_status_display(),
        'completion_date': property.completion_date
    }

    return JsonResponse(property_data)




def landing_view(request):
    """Display and filter properties"""
    # Check if user is employee
    is_employee = False
    can_sync_airtable = False
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            is_employee = profile.is_employee
            can_sync_airtable = is_employee
        except UserProfile.DoesNotExist:
            pass
    properties = Property.objects.filter(is_active=True)
    
    # Initialize filters
    filters = {
        'search': request.GET.get('search', '').strip(),
        'luxury_status': request.GET.get('luxury_status', ''),
        'min_price': request.GET.get('min_price', ''),
        'max_price': request.GET.get('max_price', ''),
        'min_bedrooms': request.GET.get('min_bedrooms', ''),
        'max_bedrooms': request.GET.get('max_bedrooms', ''),
        'min_bathrooms': request.GET.get('min_bathrooms', ''),
        'max_bathrooms': request.GET.get('max_bathrooms', ''),
        'completion_date': request.GET.get('completion_date', '')
    }

    # Apply filters
    if filters['search']:
        properties =properties.filter(
            Q(name__icontains=filters['search']) |
            Q(address__icontains=filters['search']) |
            Q(description__icontains=filters['search'])
        )
    
    if filters['luxury_status']:
        properties = properties.filter(luxury_status=filters['luxury_status'])
    
    # Filter by configuration fields (price, bedrooms, bathrooms)
    if filters['min_price']:
        try:
            min_price = float(filters['min_price'])
            properties = properties.filter(configurations__price__gte=min_price, configurations__is_available=True)
        except ValueError:
            pass
    
    if filters['max_price']:
        try:
            max_price = float(filters['max_price'])
            properties = properties.filter(configurations__price__lte=max_price, configurations__is_available=True)
        except ValueError:
            pass
    
    if filters['min_bedrooms']:
        try:
            min_bedrooms = int(filters['min_bedrooms'])
            properties = properties.filter(configurations__bedrooms__gte=min_bedrooms, configurations__is_available=True)
        except ValueError:
            pass
    
    if filters['max_bedrooms']:
        try:
            max_bedrooms = int(filters['max_bedrooms'])
            properties = properties.filter(configurations__bedrooms__lte=max_bedrooms, configurations__is_available=True)
        except ValueError:
            pass
    
    if filters['min_bathrooms']:
        try:
            min_bathrooms = int(filters['min_bathrooms'])
            properties = properties.filter(configurations__bathrooms__gte=min_bathrooms, configurations__is_available=True)
        except ValueError:
            pass
    
    if filters['max_bathrooms']:
        try:
            max_bathrooms = int(filters['max_bathrooms'])
            properties = properties.filter(configurations__bathrooms__lte=max_bathrooms, configurations__is_available=True)
        except ValueError:
            pass
    
    # Filter by completion date
    if filters['completion_date']:
        try:
            completion_date = datetime.strptime(filters['completion_date'], '%Y-%m-%d').date()
            properties = properties.filter(completion_date__lte=completion_date)
        except ValueError:
            pass
    

    # Ensure distinct results when filtering configurations
    properties = properties.distinct()

    # Get filter ranges for form inputs
    all_configs = PropertyConfiguration.objects.filter(is_available=True, property__is_active=True)
    
    # If not employee, only show properties that are in active shared lists or all if no shared lists exist
    if not is_employee:
        # This will be handled by shared link view instead
        properties = properties.none()
    
    filter_ranges = {
        'luxury_choices': Property.luxury_status.field.choices,
        'price_range': all_configs.aggregate(min_price=Min('price'), max_price=Max('price')),
        'bedroom_range': all_configs.aggregate(min_bedrooms=Min('bedrooms'), max_bedrooms=Max('bedrooms')),
        'bathroom_range': all_configs.aggregate(min_bathrooms=Min('bathrooms'), max_bathrooms=Max('bathrooms')),
        
    }
    context = {
        'properties': properties,
        'filters': filters,
        'filter_ranges': filter_ranges,
        'is_employee': is_employee,
        'can_sync_airtable': can_sync_airtable,
        'search_query': filters['search'],
    }
    return render(request, 'landing.html', context)


class PropertyPDFGenerator:
    """Utility class for generating property PDFs with professional styling"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='PropertyTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            textColor=colors.HexColor('#1f2937'),
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=12,
            textColor=colors.HexColor('#374151'),
            borderWidth=1,
            borderColor=colors.HexColor('#e5e7eb'),
            borderPadding=8,
            backColor=colors.HexColor('#f9fafb')
        ))
        
        self.styles.add(ParagraphStyle(
            name='PropertyInfo',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            textColor=colors.HexColor('#4b5563')
        ))
    
    def _download_and_process_image(self, image_url, max_width=400, max_height=300):
        """Download and process image for PDF inclusion"""
        try:
            if image_url.startswith('/'):
                # Local file
                image_path = os.path.join(settings.MEDIA_ROOT, image_url.lstrip('/'))
                if os.path.exists(image_path):
                    img = PILImage.open(image_path)
                else:
                    return None
            else:
                # Remote URL
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()
                img = PILImage.open(BytesIO(response.content))
            
            # Resize image maintaining aspect ratio
            img.thumbnail((max_width, max_height), PILImage.Resampling.LANCZOS)
            
            # Save to temporary buffer
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)
            
            return Image(buffer, width=img.width, height=img.height)
        except Exception as e:
            print(f"Error processing image {image_url}: {e}")
            return None
    
    def generate_property_pdf(self, property_obj, request):
        """Generate PDF for a single property"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch
        )
        
        story = []
        
        # Header with company info
        story.append(Paragraph("Real Estate Properties", self.styles['PropertyTitle']))
        story.append(Spacer(1, 0.2*inch))
        
        # Property name and luxury status
        title_text = property_obj.name
        if property_obj.luxury_status == 'luxurious':
            title_text += " ★ LUXURY PROPERTY"
        story.append(Paragraph(title_text, self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))
        
        # Property images
        if property_obj.images.exists():
            story.append(Paragraph("Property Images", self.styles['SectionHeader']))
            
            # Add main image
            main_image = property_obj.get_primary_image()
            if main_image:
                image_url = request.build_absolute_uri(main_image.image.url)
                img = self._download_and_process_image(image_url)
                if img:
                    story.append(img)
                    story.append(Spacer(1, 0.1*inch))
        
        # Basic information table
        story.append(Paragraph("Property Information", self.styles['SectionHeader']))
        
        basic_info = [
            ['Property Name:', property_obj.name],
            ['Address:', property_obj.address],
            ['Luxury Status:', 'Luxurious' if property_obj.luxury_status == 'luxurious' else 'Standard'],
            ['Contact:', property_obj.contact_name or 'Available on request'],
            ['Phone:', property_obj.contact_phone or 'Available on request'],
        ]
        
        basic_table = Table(basic_info, colWidths=[2*inch, 4*inch])
        basic_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(basic_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Description
        if property_obj.description:
            story.append(Paragraph("Description", self.styles['SectionHeader']))
            story.append(Paragraph(property_obj.description, self.styles['PropertyInfo']))
            story.append(Spacer(1, 0.2*inch))
        
        # Configurations
        if property_obj.configurations.exists():
            story.append(Paragraph("Available Configurations", self.styles['SectionHeader']))
            
            config_data = [['Type', 'Bedrooms', 'Bathrooms', 'Sq. Ft.', 'Price', 'Available']]
            
            for config in property_obj.configurations.all():
                price_str = f"₦{config.price:,.0f}" if config.price else "On Request"
                availability = "Yes" if config.is_available else "No"
                
                config_data.append([
                    config.type,
                    str(config.bedrooms),
                    str(config.bathrooms),
                    f"{config.square_footage:,}",
                    price_str,
                    availability
                ])
            
            config_table = Table(config_data, colWidths=[1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.2*inch, 0.8*inch])
            config_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(config_table)
            story.append(Spacer(1, 0.2*inch))
        
        # Amenities
        if property_obj.amenities.exists():
            story.append(Paragraph("Amenities & Features", self.styles['SectionHeader']))
            
            amenities_text = ", ".join([amenity.name for amenity in property_obj.amenities.all()])
            story.append(Paragraph(amenities_text, self.styles['PropertyInfo']))
            story.append(Spacer(1, 0.2*inch))
        
        # Footer
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph("Contact us for more information or to schedule a viewing.", 
                              self.styles['PropertyInfo']))
        
        # Generate PDF
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        
        return pdf
    
    def generate_comparison_pdf(self, properties, request):
        """Generate PDF comparing multiple properties"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=inch,
            bottomMargin=inch
        )
        
        story = []
        
        # Header
        story.append(Paragraph("Property Comparison Report", self.styles['PropertyTitle']))
        story.append(Spacer(1, 0.3*inch))
        
        # Summary table
        story.append(Paragraph("Properties Overview", self.styles['SectionHeader']))
        
        # Basic comparison table
        headers = ['Property', 'Address', 'Luxury', 'Min Price', 'Max Bedrooms']
        comparison_data = [headers]
        
        for prop in properties:
            min_price = prop.get_min_price()
            price_str = f"₦{min_price:,.0f}" if min_price else "On Request"
            
            comparison_data.append([
                prop.name[:25] + ('...' if len(prop.name) > 25 else ''),
                prop.address[:30] + ('...' if len(prop.address) > 30 else ''),
                '★ Luxury' if prop.luxury_status == 'luxurious' else 'Standard',
                price_str,
                str(prop.get_max_bedrooms())
            ])
        
        comparison_table = Table(comparison_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1.2*inch, 1*inch])
        comparison_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(comparison_table)
        story.append(PageBreak())
        
        # Detailed comparison for each property
        for i, prop in enumerate(properties):
            story.append(Paragraph(f"{i+1}. {prop.name}", self.styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            # Property details
            details = [
                ['Address:', prop.address],
                ['Description:', prop.description[:200] + ('...' if len(prop.description) > 200 else '') if prop.description else 'Not provided'],
                ['Contact:', f"{prop.contact_name} - {prop.contact_phone}" if prop.contact_name and prop.contact_phone else 'Available on request'],
            ]
            
            details_table = Table(details, colWidths=[1.5*inch, 5*inch])
            details_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(details_table)
            story.append(Spacer(1, 0.15*inch))
            
            # Configurations
            if prop.configurations.exists():
                config_headers = ['Type', 'Bed', 'Bath', 'Sq.Ft', 'Price']
                config_data = [config_headers]
                
                for config in prop.configurations.all()[:5]:  # Limit to 5 configs
                    price_str = f"₦{config.price:,.0f}" if config.price else "On Request"
                    config_data.append([
                        config.type,
                        str(config.bedrooms),
                        str(config.bathrooms),
                        f"{config.square_footage:,}",
                        price_str
                    ])
                
                config_table = Table(config_data, colWidths=[1.3*inch, 0.6*inch, 0.6*inch, 0.8*inch, 1.2*inch])
                config_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4b5563')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(config_table)
            
            # Amenities
            if prop.amenities.exists():
                story.append(Spacer(1, 0.1*inch))
                amenities = ", ".join([a.name for a in prop.amenities.all()[:10]])  # Limit amenities
                if prop.amenities.count() > 10:
                    amenities += f" and {prop.amenities.count() - 10} more..."
                story.append(Paragraph(f"<b>Amenities:</b> {amenities}", self.styles['PropertyInfo']))
            
            if i < len(properties) - 1:  # Don't add page break after last property
                story.append(PageBreak())
        
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        
        return pdf


@login_required
@require_http_methods(["GET"])
def download_property_pdf(request, property_id):
    """Download PDF for a specific property"""
    property_obj = get_object_or_404(Property, id=property_id, is_active=True)
    
    # Check if user has access to this property
    if not request.user.profile.is_employee:
        # Check if property is in user's shared lists
        shared_lists = SharedPropertyList.objects.filter(
            created_by=request.user,
            is_active=True,
            expires_at__gt=timezone.now(),
            properties=property_obj
        )
        if not shared_lists.exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Generate PDF
    generator = PropertyPDFGenerator()
    pdf_content = generator.generate_property_pdf(property_obj, request)
    
    # Create response
    response = HttpResponse(pdf_content, content_type='application/pdf')
    filename = f"{property_obj.slug}-details.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
@require_http_methods(["POST"])
def compare_properties(request):
    """Compare multiple properties and return comparison data"""
    try:
        data = json.loads(request.body)
        property_ids = data.get('property_ids', [])
        
        if len(property_ids) < 2:
            return JsonResponse({'error': 'At least 2 properties required for comparison'}, status=400)
        
        if len(property_ids) > 5:
            return JsonResponse({'error': 'Maximum 5 properties can be compared at once'}, status=400)
        
        # Get properties
        properties = Property.objects.filter(
            id__in=property_ids,
            is_active=True
        ).prefetch_related('configurations', 'amenities', 'images')
        
        if not request.user.profile.is_employee:
            # Filter by shared lists
            shared_lists = SharedPropertyList.objects.filter(
                created_by=request.user,
                is_active=True,
                expires_at__gt=timezone.now()
            )
            properties = properties.filter(shared_lists__in=shared_lists).distinct()
        
        if not properties.exists():
            return JsonResponse({'error': 'No accessible properties found'}, status=404)
        
        # Build comparison data
        comparison_data = []
        for prop in properties:
            configs = list(prop.configurations.all().values(
                'type', 'bedrooms', 'bathrooms', 'square_footage', 'price', 'is_available'
            ))
            amenities = list(prop.amenities.all().values_list('name', flat=True))
            images = list(prop.images.all().values('image', 'alt_text'))
            
            comparison_data.append({
                'id': prop.id,
                'name': prop.name,
                'slug': prop.slug,
                'address': prop.address,
                'description': prop.description,
                'luxury_status': prop.luxury_status,
                'contact_name': prop.contact_name,
                'contact_phone': prop.contact_phone,
                'min_price': float(prop.get_min_price()) if prop.get_min_price() else None,
                'max_bedrooms': prop.get_max_bedrooms(),
                'configurations': configs,
                'amenities': amenities,
                'images': [request.build_absolute_uri(img['image']) for img in images] if images else [],
                'primary_image': request.build_absolute_uri(prop.get_primary_image().image.url) if prop.get_primary_image() else None
            })
        
        return JsonResponse({
            'success': True,
            'properties': comparison_data,
            'comparison_url': reverse('comparison_pdf', kwargs={'property_ids': ','.join(map(str, property_ids))})
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def download_comparison_pdf(request, property_ids):
    """Download comparison PDF for multiple properties"""
    try:
        ids = [int(id.strip()) for id in property_ids.split(',') if id.strip().isdigit()]
        
        if len(ids) < 2:
            return JsonResponse({'error': 'At least 2 properties required'}, status=400)
        
        properties = Property.objects.filter(
            id__in=ids,
            is_active=True
        ).prefetch_related('configurations', 'amenities')
        
        if not request.user.profile.is_employee:
            shared_lists = SharedPropertyList.objects.filter(
                created_by=request.user,
                is_active=True,
                expires_at__gt=timezone.now()
            )
            properties = properties.filter(shared_lists__in=shared_lists).distinct()
        
        if not properties.exists():
            return JsonResponse({'error': 'No accessible properties found'}, status=404)
        
        # Generate comparison PDF
        generator = PropertyPDFGenerator()
        pdf_content = generator.generate_comparison_pdf(properties, request)
        
        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"property-comparison-{len(properties)}-properties.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    except ValueError:
        return JsonResponse({'error': 'Invalid property IDs'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)






def get_airtable_data():
    """
    Get Airtable data from cache, refresh if not available
    """
    data = cache.get('airtable_data')
    if data: 
        print('there is data in the cache')
    if not data:
        print('here')
        try:
            # Try to refresh the cache by running the management command
            logger.info("Airtable cache empty, refreshing...")
            result = call_command('sync_airtable', return_data=True)
            print('the result is ', result['properties'])
            if result:
                data = result
                cache.set('airtable_data', data, timeout=3600)
            else:
                # Return empty structure if command fails
                data = {
                    'properties': [],
                    'configurations': [],
                    'images': [],
                    'amenities': []
                }
        except Exception as e:
            logger.error(f"Failed to refresh Airtable data: {e}")
            data = {
                'properties': [],
                'configurations': [],
                'images': [],
                'amenities': []
            }
    return data

def enrich_properties_with_related_data(properties, configurations, images, amenities):
    """
    Enrich property data with related configurations, images, and amenities
    """
    enriched_properties = []
    
    for prop in properties:
        if not prop.get('is_active', True):
            continue
            
        prop_id = prop['airtable_id']
        
        # Add related configurations
        prop_configs = [config for config in configurations if config['property_id'] == prop_id]
        prop['configurations'] = prop_configs
        
        # Add related images
        prop_images = [img for img in images if img['property_id'] == prop_id]
        # Sort images by order
        prop_images.sort(key=lambda x: x.get('order', 0))
        prop['images'] = prop_images
        
        # Add related amenities
        prop_amenities = [amenity for amenity in amenities if amenity['property_id'] == prop_id]
        prop['amenities'] = prop_amenities
        
        # Add helper methods similar to Django model methods
        prop['get_min_price'] = get_property_min_price(prop_configs)
        
        enriched_properties.append(prop)
    
    return enriched_properties

@login_required
@require_http_methods(["GET"])
def airtable_property_detail_api(request, property_id):
    """
    API endpoint to get detailed property information from Airtable cache
    """
    try:
        # Get Airtable data from cache
        airtable_data = get_airtable_data()  # Reuse the function from landing_view
        print("airtable_data is22 ", airtable_data)
        
        # Find the property by airtable_id
        property_data = None
        for prop in airtable_data.get('properties', []):
            if prop.get('airtable_id') == property_id:
                property_data = prop
                break
        
        if not property_data:
            return JsonResponse({'error': 'Property not found'}, status=404)
        
        # Get related data
        configurations = airtable_data.get('configurations', [])
        images = airtable_data.get('images', [])
        amenities = airtable_data.get('amenities', [])
        
        # Filter related data for this property
        prop_configs = [config for config in configurations if config['property_id'] == property_id]
        prop_images = [img for img in images if img['property_id'] == property_id]
        prop_amenities = [amenity for amenity in amenities if amenity['property_id'] == property_id]
        
        # Sort images by order
        prop_images.sort(key=lambda x: x.get('order', 0))
        
        # Format the response data
        response_data = {
            'id': property_data.get('airtable_id'),
            'name': property_data.get('name'),
            'address': property_data.get('address'),
            'description': property_data.get('description'),
            'luxury_status': property_data.get('luxury_status'),
            "latitude": property_data.get('latitude'),
            "longitude": property_data.get('longitude'),
            'contact': f"{property_data.get('contact_name', '')} - {property_data.get('contact_phone', '')}".strip(' - '),
            'images': [img.get('image_url') for img in prop_images if img.get('image_url')],
            'configurations': [],
            'amenities': [amenity.get('name') for amenity in prop_amenities if amenity.get('name')]
            
        }
        
        # Format configurations with proper price handling
        for config in prop_configs:
            if config.get('is_available', True):
                formatted_config = {
                    'bedrooms': config.get('bedrooms', 0),
                    'bathrooms': config.get('bathrooms', 0),
                    'square_footage': config.get('square_footage', 0),
                    'type': config.get('type', ''),
                    'is_available': config.get('is_available', True)
                }
                
                # Handle price formatting
                if config.get('price'):
                    try:
                        if isinstance(config['price'], str):
                            # Clean the price string
                            clean_price = config['price'].replace('₦', '').replace(',', '').strip()
                            if clean_price and clean_price.replace('.', '').isdigit():
                                formatted_config['price'] = f"₦{float(clean_price):,.0f}"
                            else:
                                formatted_config['price'] = 'TBD'
                        else:
                            formatted_config['price'] = f"₦{float(config['price']):,.0f}"
                    except (ValueError, TypeError):
                        formatted_config['price'] = 'TBD'
                else:
                    formatted_config['price'] = 'TBD'
                
                response_data['configurations'].append(formatted_config)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in airtable_property_detail_api: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["GET"])
def airtable_all_properties_api(request):
    """
    API endpoint to get detailed information for all properties from Airtable cache
    """
    try:
        # Get Airtable data from cache
        airtable_data = get_airtable_data()  # Assuming get_airtable_data() is replaced with direct cache access
        
        # Extract data
        properties = airtable_data.get('properties', [])
        configurations = airtable_data.get('configurations', [])
        images = airtable_data.get('images', [])
        amenities = airtable_data.get('amenities', [])
        
        # Format response data for all properties
        response_data = []
        
        for property_data in properties:
            # Filter related data for this property
            prop_configs = [config for config in configurations if config['property_id'] == property_data['airtable_id']]
            prop_images = [img for img in images if img['property_id'] == property_data['airtable_id']]
            prop_amenities = [amenity for amenity in amenities if amenity['property_id'] == property_data['airtable_id']]
            
            # Sort images by order
            prop_images.sort(key=lambda x: x.get('order', 0))
            
            # Format property details
            property_response = {
                'id': property_data.get('airtable_id'),
                'name': property_data.get('name'),
                'address': property_data.get('address'),
                'description': property_data.get('description'),
                "latitude": property_data.get('latitude'),
                "longitude": property_data.get('longitude'),
                'luxury_status': property_data.get('luxury_status'),
                'contact': f"{property_data.get('contact_name', '')} - {property_data.get('contact_phone', '')}".strip(' - '),
                'images': [img.get('image_url') for img in prop_images if img.get('image_url')],
                'configurations': [],
                'amenities': [amenity.get('name') for amenity in prop_amenities if amenity.get('name')]
            }
            
            # Format configurations with proper price handling
            for config in prop_configs:
                if config.get('is_available', True):
                    formatted_config = {
                        'bedrooms': config.get('bedrooms', 0),
                        'bathrooms': config.get('bathrooms', 0),
                        'square_footage': config.get('square_footage', 0),
                        'type': config.get('type', ''),
                        'is_available': config.get('is_available', True)
                    }
                    
                    # Handle price formatting
                    if config.get('price'):
                        try:
                            if isinstance(config['price'], str):
                                # Clean the price string
                                clean_price = config['price'].replace('₦', '').replace(',', '').strip()
                                if clean_price and clean_price.replace('.', '').isdigit():
                                    formatted_config['price'] = f"₦{float(clean_price):,.0f}"
                                else:
                                    formatted_config['price'] = 'TBD'
                            else:
                                formatted_config['price'] = f"₦{float(config['price']):,.0f}"
                        except (ValueError, TypeError):
                            formatted_config['price'] = 'TBD'
                    else:
                        formatted_config['price'] = 'TBD'
                    
                    property_response['configurations'].append(formatted_config)
            
            response_data.append(property_response)
        
        return JsonResponse(response_data, safe=False)  # safe=False to allow list serialization
        
    except Exception as e:
        logger.error(f"Error in airtable_all_properties_api: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
    
