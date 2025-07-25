from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from decimal import Decimal
from .models import Property, PropertyConfiguration, PropertyImage, PropertyAmenity

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'name', 'address', 'description', 'latitude', 'longitude',
            'contact_name', 'contact_phone', 'thumbnail', 'brochure', 'luxury_status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
        }

class PropertyQuickAddForm(forms.ModelForm):
    """Simplified form for quick property addition"""
    amenities = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Enter amenities separated by commas'}),
        help_text="Separate amenities with commas",
        required=False
    )

    class Meta:
        model = Property
        fields = [
            'name', 'address', 'description', 'latitude', 'longitude',
            'contact_name', 'contact_phone', 'thumbnail', 'brochure', 'luxury_status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'latitude': forms.NumberInput(attrs={'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'step': 'any'}),
        }

    def save(self, commit=True):
        instance = super().save(commit)
        if commit:
            amenities_text = self.cleaned_data.get('amenities', '')
            if amenities_text:
                amenities = [a.strip() for a in amenities_text.split(',') if a.strip()]
                for amenity in amenities:
                    PropertyAmenity.objects.create(property=instance, name=amenity)
        return instance

class PropertyConfigurationForm(forms.ModelForm):
    price = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 1800000000'}),
        help_text="Enter price without commas (e.g., 1800000000)"
    )

    class Meta:
        model = PropertyConfiguration
        fields = ['type', 'bedrooms', 'bathrooms', 'square_footage', 'price']
        widgets = {
            'type': forms.TextInput(attrs={'placeholder': 'e.g., Standard'}),
            'bedrooms': forms.NumberInput(attrs={'min': 0}),
            'bathrooms': forms.NumberInput(attrs={'min': 1}),
            'square_footage': forms.NumberInput(attrs={'min': 1}),
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price:
            cleaned_price = price.replace(',', '').replace('₦', '').strip()
            try:
                decimal_price = Decimal(cleaned_price)
                if decimal_price < 0:
                    raise ValidationError("Price cannot be negative.")
                if decimal_price > Decimal('9999999999.99'):
                    raise ValidationError("Price exceeds maximum allowed value (9999999999.99).")
                return decimal_price
            except (ValueError, TypeError, Decimal.InvalidOperation):
                raise ValidationError("Price must be a valid number (e.g., 1800000000 or 1800000000.00).")
        return None

class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'multiple': False}),
        }

# Create formsets
PropertyConfigurationFormSet = inlineformset_factory(
    Property,
    PropertyConfiguration,
    form=PropertyConfigurationForm,
    extra=1,
    can_delete=True
)

PropertyImageFormSet = inlineformset_factory(
    Property,
    PropertyImage,
    form=PropertyImageForm,
    extra=1,
    can_delete=True
)