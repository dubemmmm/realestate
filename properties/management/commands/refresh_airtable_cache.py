# Create this file: management/commands/refresh_airtable_cache.py

import logging
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.core.cache import cache

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Refresh the Airtable data cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh even if cache is not expired',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=3600,
            help='Cache timeout in seconds (default: 3600)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting Airtable cache refresh...')
        )
        
        try:
            # Check if we should refresh
            if not options['force']:
                existing_data = cache.get('airtable_data')
                if existing_data:
                    self.stdout.write('Cache exists and --force not specified. Skipping refresh.')
                    return
            
            # Refresh the data using the existing command
            result = call_command('fetch_airtable_data', return_data=True)
            
            if result:
                # Update cache with custom timeout if specified
                cache.set('airtable_data', result, timeout=options['timeout'])
                
                # Display summary
                properties_count = len(result.get('properties', []))
                configs_count = len(result.get('configurations', []))
                images_count = len(result.get('images', []))
                amenities_count = len(result.get('amenities', []))
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Cache refreshed successfully!\n'
                        f'Properties: {properties_count}\n'
                        f'Configurations: {configs_count}\n'
                        f'Images: {images_count}\n'
                        f'Amenities: {amenities_count}\n'
                        f'Cache timeout: {options["timeout"]} seconds'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Failed to refresh cache - no data returned')
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error refreshing cache: {e}')
            )
            logger.error(f'Cache refresh error: {e}', exc_info=True)