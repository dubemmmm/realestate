from django.contrib import admin
from django.utils.html import format_html
from .models import Property, PropertyConfiguration, PropertyImage, PropertyAmenity

class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 3
    fields = ['image', 'alt_text', 'order']

class PropertyConfigurationInline(admin.TabularInline):
    model = PropertyConfiguration
    extra = 2
    fields = ['type', 'bedrooms', 'bathrooms', 'square_footage', 'price', 'is_available']

class PropertyAmenityInline(admin.TabularInline):
    model = PropertyAmenity
    extra = 3
    fields = ['name']

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'get_min_price', 'contact_name', 'is_active', 'created_at', 'luxury_status']
    list_filter = ['is_active', 'created_at', 'luxury_status']
    search_fields = ['name', 'address', 'contact_name']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [PropertyConfigurationInline, PropertyImageInline, PropertyAmenityInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'address', 'description', 'is_active', 'luxury_status')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Contact Information', {
            'fields': ('contact_name', 'contact_phone')
        }),
        ('Media', {
            'fields': ('thumbnail', 'brochure')
        }),
    )

    def get_min_price(self, obj):
        min_price = obj.get_min_price()
        if min_price:
            return f"₦{min_price:,.2f}"
        return "TBD"
    get_min_price.short_description = "Min Price"