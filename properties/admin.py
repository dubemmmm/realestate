from django.contrib import admin
from django.utils.html import format_html
from .models import Property, PropertyConfiguration, PropertyImage, PropertyAmenity, SharedPropertyList, UserProfile
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

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

class SharedPropertyListInline(admin.TabularInline):
    model = SharedPropertyList.properties.through
    extra = 0

@admin.register(SharedPropertyList)
class SharedPropertyListAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'get_property_count', 'view_count', 'is_active', 'is_expired_display', 'created_at', 'expires_at']
    list_filter = ['is_active', 'created_at', 'expires_at', 'created_by']
    search_fields = ['name', 'token', 'created_by__username']
    readonly_fields = ['token', 'view_count', 'created_at']
    filter_horizontal = ['properties']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'token', 'is_active')
        }),
        ('Sharing Details', {
            'fields': ('created_by', 'expires_at', 'view_count', 'created_at')
        }),
        ('Properties', {
            'fields': ('properties',)
        }),
    )

    def get_property_count(self, obj):
        return obj.properties.count()
    get_property_count.short_description = "Properties"

    def is_expired_display(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Active</span>')
    is_expired_display.short_description = "Status"

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ['role', 'phone', 'is_employee', ]

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_role', 'get_is_employee', 'is_staff']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'profile__role', 'profile__is_employee']

    def get_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return "No Profile"
    get_role.short_description = "Role"

    def get_is_employee(self, obj):
        try:
            return obj.profile.is_employee
        except UserProfile.DoesNotExist:
            return False
    get_is_employee.short_description = "Employee"
    get_is_employee.boolean = True

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'is_employee', 'created_at']
    list_filter = ['role', 'is_employee', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'phone']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Profile Details', {
            'fields': ('role', 'phone', 'is_employee',)
        }),
    )