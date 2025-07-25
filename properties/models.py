from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import os

def property_image_path(instance, filename):
    """Generate upload path for property images"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"property_images/{instance.property.slug}/{filename}"


def brochure_path(instance, filename):
    """Generate upload path for brochures"""
    ext = filename.split('.')[-1]
    filename = f"brochure.{ext}"
    return f"brochures/{instance.slug}/{filename}"

def property_thumbnail_path(instance, filename):
    """Generate upload path for Property thumbnail"""
    return f"property_thumbnails/{instance.slug}/{filename}"

class Property(models.Model):
    LUXURY_CHOICES = (
        ('luxurious', 'Luxurious'),
        ('non_luxurious', 'Non-Luxurious'),
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    address = models.TextField()
    description = models.TextField()
    latitude = models.DecimalField(
        max_digits=20,
        decimal_places=15,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.DecimalField(
        max_digits=20, 
        decimal_places=15,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    contact_name = models.CharField(max_length=100)
    contact_phone = models.CharField(max_length=20)
    brochure = models.FileField(upload_to=brochure_path, blank=True, null=True)
    thumbnail = models.ImageField(upload_to=property_thumbnail_path, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    luxury_status = models.CharField(
        max_length=20,
        choices=LUXURY_CHOICES,
        default='non_luxurious',
    )

    class Meta:
        verbose_name_plural = "Properties"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_min_price(self):
        """Get minimum price from configurations"""
        configs = self.configurations.filter(price__isnull=False)
        if configs:
            return min(config.price for config in configs if config.price)
        return None

    def get_max_bedrooms(self):
        """Get maximum bedrooms from configurations"""
        configs = self.configurations.all()
        if configs:
            return max(config.bedrooms for config in configs)
        return 0

class PropertyConfiguration(models.Model):
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='configurations'
    )
    type = models.CharField(max_length=100)  # e.g., "Studio", "1BR", "2BR"
    bedrooms = models.PositiveIntegerField(default=0)
    bathrooms = models.PositiveIntegerField(default=1)
    square_footage = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.property.name} - {self.type}"

    class Meta:
        ordering = ['bedrooms', 'price']

class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(upload_to=property_image_path)
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.property.name} - Image {self.order}"

class PropertyAmenity(models.Model):
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='amenities'
    )
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Property Amenities"

    def __str__(self):
        return f"{self.property.name} - {self.name}"