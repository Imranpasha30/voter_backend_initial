from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

class GeocodingService:
    def __init__(self):
        # Use your app name as user_agent
        self.geolocator = Nominatim(user_agent="political_survey_app_v1.0")
    
    def get_address_from_coordinates(self, latitude: float, longitude: float):
        """
        Reverse geocode coordinates to get area name
        Returns: dict with area, city, state, country
        """
        try:
            # Add delay to respect rate limits (1 request per second for Nominatim)
            time.sleep(1)
            
            location = self.geolocator.reverse(f"{latitude}, {longitude}", language='en')
            
            if location and location.raw:
                address = location.raw.get('address', {})
                
                return {
                    'area': (
                        address.get('suburb') or 
                        address.get('neighbourhood') or 
                        address.get('hamlet') or
                        address.get('quarter') or
                        address.get('village') or
                        'Unknown'
                    ),
                    'colony': address.get('residential') or address.get('suburb'),
                    'city': (
                        address.get('city') or 
                        address.get('town') or 
                        address.get('municipality')
                    ),
                    'district': address.get('state_district'),
                    'state': address.get('state'),
                    'country': address.get('country'),
                    'postcode': address.get('postcode'),
                    'full_address': location.address
                }
            
            return None
            
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Geocoding error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

# Initialize service
geocoding_service = GeocodingService()
