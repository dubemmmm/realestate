from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from decimal import Decimal
from .models import Property, PropertyConfiguration, PropertyImage, PropertyAmenity
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile

# class PropertyForm(forms.ModelForm):
#     class Meta:
#         model = Property
#         fields = [
#             'name', 'address', 'description', 'latitude', 'longitude',
#             'contact_name', 'contact_phone', 'thumbnail', 'brochure', 'luxury_status'
#         ]
#         widgets = {
#             'description': forms.Textarea(attrs={'rows': 4}),
#             'latitude': forms.NumberInput(attrs={'step': 'any'}),
#             'longitude': forms.NumberInput(attrs={'step': 'any'}),
#         }

# class PropertyQuickAddForm(forms.ModelForm):
#     """Simplified form for quick property addition"""
#     amenities = forms.CharField(
#         widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Enter amenities separated by commas'}),
#         help_text="Separate amenities with commas",
#         required=False
#     )

#     class Meta:
#         model = Property
#         fields = [
#             'name', 'address', 'description', 'latitude', 'longitude',
#             'contact_name', 'contact_phone', 'thumbnail', 'brochure', 'luxury_status'
#         ]
#         widgets = {
#             'description': forms.Textarea(attrs={'rows': 4}),
#             'latitude': forms.NumberInput(attrs={'step': 'any'}),
#             'longitude': forms.NumberInput(attrs={'step': 'any'}),
#         }

#     def save(self, commit=True):
#         instance = super().save(commit)
#         if commit:
#             amenities_text = self.cleaned_data.get('amenities', '')
#             if amenities_text:
#                 amenities = [a.strip() for a in amenities_text.split(',') if a.strip()]
#                 for amenity in amenities:
#                     PropertyAmenity.objects.create(property=instance, name=amenity)
#         return instance

# class PropertyConfigurationForm(forms.ModelForm):
#     price = forms.CharField(
#         max_length=20,
#         required=False,
#         widget=forms.TextInput(attrs={'placeholder': 'e.g., 1800000000'}),
#         help_text="Enter price without commas (e.g., 1800000000)"
#     )

#     class Meta:
#         model = PropertyConfiguration
#         fields = ['type', 'bedrooms', 'bathrooms', 'square_footage', 'price']
#         widgets = {
#             'type': forms.TextInput(attrs={'placeholder': 'e.g., Standard'}),
#             'bedrooms': forms.NumberInput(attrs={'min': 0}),
#             'bathrooms': forms.NumberInput(attrs={'min': 1}),
#             'square_footage': forms.NumberInput(attrs={'min': 1}),
#         }

#     def clean_price(self):
#         price = self.cleaned_data.get('price')
#         if price:
#             cleaned_price = price.replace(',', '').replace('₦', '').strip()
#             try:
#                 decimal_price = Decimal(cleaned_price)
#                 if decimal_price < 0:
#                     raise ValidationError("Price cannot be negative.")
#                 if decimal_price > Decimal('9999999999.99'):
#                     raise ValidationError("Price exceeds maximum allowed value (9999999999.99).")
#                 return decimal_price
#             except (ValueError, TypeError, Decimal.InvalidOperation):
#                 raise ValidationError("Price must be a valid number (e.g., 1800000000 or 1800000000.00).")
#         return None

# class PropertyImageForm(forms.ModelForm):
#     class Meta:
#         model = PropertyImage
#         fields = ['image']
#         widgets = {
#             'image': forms.ClearableFileInput(attrs={'multiple': False}),
#         }

# # Create formsets
# PropertyConfigurationFormSet = inlineformset_factory(
#     Property,
#     PropertyConfiguration,
#     form=PropertyConfigurationForm,
#     extra=1,
#     can_delete=True
# )

# PropertyImageFormSet = inlineformset_factory(
#     Property,
#     PropertyImage,
#     form=PropertyImageForm,
#     extra=1,
#     can_delete=True
# )



class CustomUserCreationForm(BaseUserCreationForm):
    """Extended user creation form with profile fields"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter your email address'
        })
    )
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter your first name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter your last name'
        })
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Enter your phone number (optional)'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Choose a username'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add CSS classes to password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Create a password'
        })
        
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Confirm your password'
        })
        
        # Update field labels
        self.fields['username'].label = 'Username'
        self.fields['first_name'].label = 'First Name'
        self.fields['last_name'].label = 'Last Name'
        self.fields['email'].label = 'Email Address'
        self.fields['phone'].label = 'Phone Number'
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Confirm Password'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create or update the user profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.phone = self.cleaned_data.get('phone', '')
            profile.save()
        
        return user

class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information"""
    
    class Meta:
        model = UserProfile
        fields = ['phone', 'role']
        widgets = {
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Enter your phone number'
            }),
            'role': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            })
        }

class EmployeeUserCreationForm(CustomUserCreationForm):
    """Form for admin to create employee users"""
    
    is_employee = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox h-4 w-4 text-blue-600 rounded focus:ring-blue-500'
        })
    )
    
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        if commit:
            user.save()
            # Create or update the user profile with admin settings
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.phone = self.cleaned_data.get('phone', '')
            profile.is_employee = self.cleaned_data.get('is_employee', False)
            profile.can_share_properties = self.cleaned_data.get('can_share_properties', False)
            profile.role = self.cleaned_data.get('role', 'viewer')
            profile.save()
        
        return user