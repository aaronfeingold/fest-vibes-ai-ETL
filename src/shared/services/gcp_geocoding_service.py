"""
Geocoding service for converting addresses to geographic coordinates.
"""

import os
from typing import Dict

import aiohttp

from src.shared.utils.configs import base_configs
from src.shared.utils.logger import logger


class GeocodingService:
    """
    A service for geocoding addresses using the Google Maps Geocoding API.

    This class provides functionality to convert addresses into geographic coordinates
    (latitude and longitude). If the address is empty, invalid, or for streaming events,
    it defaults to the coordinates of New Orleans, Louisiana.
    """

    def __init__(self):
        """Initialize the geocoding service."""
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.default_coords = base_configs["default_coords"]

    async def geocode_address(self, address: str) -> Dict[str, float]:
        """
        Geocodes a given address to retrieve its latitude and longitude.

        If the address is empty, invalid, or corresponds to a streaming event,
        default coordinates for New Orleans (NOLA) are returned.

        Args:
            address (str): The address to geocode.

        Returns:
            dict: A dictionary containing the latitude and longitude of the
                  geocoded address. If geocoding fails, default coordinates
                  are returned in the format:
                  {
                      "latitude": float,
                      "longitude": float
                  }
        """
        # Check if address is empty or for streaming events
        if not address or address.strip() == "" or ".Streaming" in address:
            logger.info(
                f"Address is empty or for streaming event: {address=}. Using default coordinates."
            )
            # Return default coordinates
            return self.default_coords

        logger.info(f"Geocoding {address=}")

        if not self.api_key:
            logger.warning(
                "Google Maps API key not configured. Using default coordinates."
            )
            return self.default_coords

        params = {"address": address, "key": self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    data = await response.json()

                    if data["status"] == "OK":
                        result = data["results"][0]
                        lat = result["geometry"]["location"]["lat"]
                        lng = result["geometry"]["location"]["lng"]

                        return {"latitude": lat, "longitude": lng}
                    else:
                        logger.warning(
                            f"Geocoding failed: {data['status']} - "
                            f"{data.get('error_message')}. Using default coordinates."
                        )
                        # Return default coordinates instead of raising an error
                        return self.default_coords
        except Exception as e:
            logger.warning(
                f"Exception during geocoding: {str(e)}. Using default coordinates."
            )
            # Return default coordinates instead of raising an error
            return self.default_coords


# Create a global geocoding service instance
geocoding_service = GeocodingService()
