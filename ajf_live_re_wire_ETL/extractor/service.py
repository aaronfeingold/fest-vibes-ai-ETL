"""
Scraper service for extracting event data from a sample website.
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple
from urllib.error import HTTPError, URLError

import aiohttp
from bs4 import BeautifulSoup, NavigableString, PageElement, Tag

from ajf_live_re_wire_ETL.shared.schemas import (
    ArtistData,
    EventData,
    EventDTO,
    VenueData,
)
from ajf_live_re_wire_ETL.shared.utils.configs import base_configs
from ajf_live_re_wire_ETL.shared.utils.errors import ScrapingError
from ajf_live_re_wire_ETL.shared.utils.helpers import generate_url
from ajf_live_re_wire_ETL.shared.utils.logger import logger
from ajf_live_re_wire_ETL.shared.utils.types import ErrorType


class ScraperService:
    """
    Scraper for extracting event data from a sample website.
    """

    def __init__(self):
        """Initialize the scraper."""
        self.session = None
        self.seen_urls = set()

    async def run(self, params: Dict[str, str]) -> List[EventDTO]:
        """
        Run the scraper.

        Args:
            params: Dictionary of query parameters

        Returns:
            List of EventDTO objects
        """
        try:
            soup = await self.make_soup(
                endpoint=base_configs["default_endpoint"], params=params
            )
            return await self.parse_base_html(soup, params["date"])
        except ScrapingError:
            raise
        except Exception as e:
            logger.error(
                f"A {ErrorType.GENERAL_ERROR.value} occurred while scraping: {e}"
            )
            raise ScrapingError(
                message=f"An unexpected error occurred while scraping: {e}",
                error_type=ErrorType.GENERAL_ERROR,
                status_code=500,
            )

    async def fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from a URL.

        Args:
            url: URL to fetch

        Returns:
            HTML content as a string
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            async with self.session.get(
                url,
                headers=base_configs["default_headers"],
                max_redirects=10,  # Limit number of redirects
                timeout=aiohttp.ClientTimeout(total=30),  # 30 second timeout
            ) as response:
                if response.status != 200:
                    raise ScrapingError(
                        message=f"Failed to fetch data: HTTP {response.status}",
                        error_type=ErrorType.HTTP_ERROR,
                        status_code=response.status,
                    )
                return await response.text()
        except ScrapingError:
            raise
        except HTTPError as e:
            raise ScrapingError(
                message=f"Failed to fetch data: HTTP {e.code}",
                error_type=ErrorType.HTTP_ERROR,
                status_code=e.code,
            )
        except URLError as e:
            raise ScrapingError(
                message=f"Failed to connect to server: {e.reason}",
                error_type=ErrorType.URL_ERROR,
                status_code=503,
            )
        except aiohttp.ClientError as e:
            if "too many redirects" in str(e).lower():
                logger.warning(f"Too many redirects for URL: {url}")
                return "<html><body><div class='error'>Too many redirects</div></body></html>"
            raise ScrapingError(
                message=f"Failed to fetch data: {str(e)}",
                error_type=ErrorType.FETCH_ERROR,
                status_code=500,
            )
        except Exception as e:
            if "too many redirects" in str(e).lower():
                logger.warning(f"Too many redirects for URL: {url}")
                return "<html><body><div class='error'>Too many redirects</div></body></html>"
            raise ScrapingError(
                message=f"An unexpected error occurred while fetching data: {e}",
                error_type=ErrorType.FETCH_ERROR,
                status_code=500,
            )

    async def make_soup(
        self, endpoint: str | None = None, params: Dict[str, str] = {}
    ) -> BeautifulSoup:
        """
        Create a BeautifulSoup object from an endpoint.

        Args:
            endpoint: Endpoint to fetch
            params: Query parameters

        Returns:
            BeautifulSoup object
        """
        try:
            html = await self.fetch_html(
                generate_url(
                    endpoint=endpoint,
                    params=params,
                )
            )
            soup = BeautifulSoup(html, "html.parser")

            # Check if we got our "too many redirects" placeholder
            error_div = soup.find("div", class_="error")
            if error_div and error_div.text == "Too many redirects":
                logger.warning(f"Skipping URL due to too many redirects: {endpoint}")
                # Return a minimal soup that will be handled appropriately by calling methods
                return BeautifulSoup("<html><body></body></html>", "html.parser")

            return soup
        except ScrapingError as e:
            raise ScrapingError(
                error_type=e.error_type,
                message=f"Failed to create soup from html: {e.message}",
                status_code=e.status_code,
            )
        except Exception as e:
            raise ScrapingError(
                message=f"An exception making soup: {e}",
                error_type=ErrorType.SOUP_ERROR,
                status_code=500,
            )

    def get_text_or_default(
        self,
        element: PageElement | Tag | NavigableString,
        tag: str,
        class_name: str,
        default: str = "",
    ) -> str:
        """
        Get text from a BeautifulSoup element or return a default value.

        Args:
            element: BeautifulSoup element to search in. Can be any BeautifulSoup element type
                   (PageElement, Tag, or NavigableString) that supports the .find() method.
            tag: HTML tag to find (e.g. 'div', 'span', 'p')
            class_name: Class name to search for (e.g. 'title', 'description')
            default: Default value to return if element not found

        Returns:
            str: Text content of the found element (stripped of whitespace) or default value
        """
        found = element.find(tag, class_=class_name)
        if found and hasattr(found, "text"):
            return found.text.strip()
        return default

    async def get_venue_data(self, wwoz_venue_href: str, venue_name: str) -> VenueData:
        """
        Deep crawl venue page to get additional details.

        Args:
            wwoz_venue_href: URL path for the venue
            venue_name: Name of the venue

        Returns:
            VenueData object with venue details
        """
        logger.info(f"Fetching venue data for {venue_name}")

        if wwoz_venue_href in self.seen_urls:
            # don't build details again, we already have seen this URL today
            logger.debug(f"Already processed venue URL: {wwoz_venue_href}")
            return VenueData(name=venue_name, wwoz_venue_href=wwoz_venue_href)

        self.seen_urls.add(wwoz_venue_href)
        soup = await self.make_soup(wwoz_venue_href)
        venue_data = VenueData(
            name=venue_name,
            wwoz_venue_href=wwoz_venue_href,
            is_active=True,
        )

        content_div = soup.find("div", class_="content")
        if content_div is not None:
            try:
                venue_data.thoroughfare = self.get_text_or_default(
                    content_div, "div", "thoroughfare"
                )
                venue_data.locality = self.get_text_or_default(
                    content_div, "span", "locality"
                )
                venue_data.state = self.get_text_or_default(
                    content_div, "span", "state"
                )
                venue_data.postal_code = self.get_text_or_default(
                    content_div, "span", "postal_code"
                )

                website_div = content_div.find(
                    "div", class_="field-name-field-url"
                )  # this div is not always present, if it is, then get the href

                if website_div is not None:
                    website_link = website_div.find("div", class_="field-item even")
                    venue_data.website = (
                        website_link.find("a")["href"] if website_link else ""
                    )

                phone_section = content_div.find("div", class_="field-name-field-phone")
                if phone_section is not None:
                    venue_data.phone_number = phone_section.find("a").text.strip()

                # create a full address to transfer to geolocation API
                venue_data.full_address = f"{venue_data.thoroughfare}, {venue_data.locality}, {venue_data.state} {venue_data.postal_code}"

                # find out if business is still active
                status_div = content_div.find(
                    "div", class_="field-name-field-organization-status"
                )
                if status_div is not None:
                    status = self.get_text_or_default(
                        status_div, "div", "field-item even", "Active"
                    )
                    venue_data.is_active = True if status.lower() == "active" else False
            except Exception as e:
                logger.warning(f"Error parsing venue details for {venue_name}: {e}")
                raise ScrapingError(
                    message=f"Failed to scrape venue content section: {e}",
                    error_type=ErrorType.PARSE_ERROR,
                    status_code=400,
                )

        return venue_data

    def is_attribute_non_empty(self, obj, attr_name):
        """
        Check if an attribute exists and is not empty.

        Args:
            obj: Object to check
            attr_name: Name of the attribute to check

        Returns:
            True if the attribute exists and is not empty, False otherwise
        """
        if hasattr(obj, attr_name):  # Check if the attribute exists
            value = getattr(obj, attr_name)  # Get the attribute value
            return (
                isinstance(value, str) and value != ""
            )  # Check if it's a non-empty string
        return False

    async def get_artist_data(
        self, wwoz_artist_href: str, artist_name: str
    ) -> ArtistData:
        """
        Deep crawl artist page to get additional details.

        Args:
            wwoz_artist_href: URL path for the artist
            artist_name: Name of the artist

        Returns:
            ArtistData object with artist details
        """
        logger.info(f"Fetching artist data for {artist_name}")

        if wwoz_artist_href in self.seen_urls:
            return ArtistData(
                name=artist_name,
                wwoz_artist_href=wwoz_artist_href,
            )

        self.seen_urls.add(wwoz_artist_href)
        soup = await self.make_soup(wwoz_artist_href)

        artist_data = ArtistData(
            name=artist_name,
            wwoz_artist_href=wwoz_artist_href,
        )

        content_div = soup.select_one(".content")

        if content_div is not None:
            try:
                genres_div = content_div.find("div", class_="field-name-field-genres")
                if genres_div is not None:
                    artist_data.genres = [
                        genre.text.strip() for genre in genres_div.find_all("a")
                    ]

                related_artists_div = content_div.find(
                    "div", class_="field field-name-field-related-acts"
                )

                if related_artists_div is not None:
                    related_artists_list = related_artists_div.find(
                        "span", class_="textformatter-list"
                    )
                    if related_artists_list:
                        artist_data.related_artists = [
                            related_artist.text.strip()
                            for related_artist in related_artists_list.find_all("a")
                        ]
                # TODO: GRAB THE ARTIST'S DESCRIPTION HERE (w/ OPENAI to Summarize perhaps?)
            except Exception as e:
                raise ScrapingError(
                    message=f"Failed to scrape artist content section: {e}",
                    error_type=ErrorType.PARSE_ERROR,
                    status_code=400,
                )

        return artist_data

    async def get_event_data(
        self, wwoz_event_href: str, artist_name: str, event_date: datetime
    ) -> Tuple[EventData, ArtistData]:
        """
        Deep crawl event page to get additional details.

        Args:
            wwoz_event_href: URL path for the event
            artist_name: Name of the artist
            event_date: Date of the event

        Returns:
            Tuple of (EventData, ArtistData) with event and artist details
        """
        logger.info(f"Fetching event data for {artist_name}")

        if wwoz_event_href in self.seen_urls:
            return EventData(
                event_date=event_date,
                wwoz_event_href=wwoz_event_href,
                event_artist=artist_name,
            ), ArtistData(name=artist_name)

        self.seen_urls.add(wwoz_event_href)
        soup = await self.make_soup(wwoz_event_href)

        event_data = EventData(
            event_date=event_date,
            wwoz_event_href=wwoz_event_href,
            event_artist=artist_name,
        )

        event_div = soup.find("div", class_="content")
        if event_div is not None:
            description_div = event_div.find("div", class_="field-name-body")
            try:
                if description_div:
                    description_field = description_div.find(
                        "div", class_="field-item even"
                    )
                    if description_field and description_field.find("p"):
                        # TODO: USE OPENAI API TO EXTRACT EVENT DETAILS FROM DESCRIPTION
                        description = description_field.find("p").text.strip()
                        # add whatever description we have to the event data
                        event_data.description = description
            except Exception as e:
                # if we error getting these things, who cares, just pass and default to no description
                logger.warning(f"Failed to scrape event description: {e}")
                pass

            related_artists_div = event_div.find(
                "div", class_=re.compile(r"field-name-field-related-acts")
            )
            # find the artist name in the related artist links if links exist
            related_artists = []
            if related_artists_div:
                related_artists_list = related_artists_div.find(
                    "span", class_="textformatter-list"
                )
                if related_artists_list:
                    # add all other artists in list that do match the artist as 'related artists'
                    for link in related_artists_list.find_all("a"):
                        if link.text.strip() not in artist_name:
                            related_artists.append(
                                {
                                    "name": link.text.strip(),
                                    "wwoz_artist_href": link["href"],
                                }
                            )
                        else:
                            # sometimes the artist name of the event artist has no link
                            # if it does, let's grab some more info, whatever there is, hopefully some genres
                            event_data.wwoz_artist_href = link["href"]
            # copy the related artists to the event data if any
            event_data.related_artists = related_artists

        artist_data = ArtistData(name=artist_name)

        if self.is_attribute_non_empty(event_data, "wwoz_artist_href"):
            artist_data = await self.get_artist_data(
                event_data.wwoz_artist_href, artist_name
            )

        # for now, let's just get the genres of the event artist if we have this info scraped
        # and give the event some genres for people to search by
        try:
            genre_list_empty = True
            if hasattr(artist_data, "genres"):  # Check if the attribute exists
                value = getattr(artist_data, "genres")  # Get the attribute value
                genre_list_empty = (
                    isinstance(value, tuple) and len(value) == 0
                ) or len(value) == 0
                if not genre_list_empty:
                    event_data.genres = artist_data.genres
        except Exception as e:
            raise ScrapingError(
                message=f"Failed to add artist's genres to the event description: {e}",
                error_type=ErrorType.PARSE_ERROR,
                status_code=400,
            )

        return event_data, artist_data

    def parse_event_performance_time(self, date_str: str, time_str: str) -> datetime:
        """
        Parse the event performance time.

        Args:
            date_str: Date string
            time_str: Time string

        Returns:
            Datetime object with the performance time
        """
        try:
            time_stripped = time_str.strip()
            time_pattern = r"\b\d{1,2}:\d{2}\s?(am|pm)\b"
            match = re.search(time_pattern, time_stripped, re.IGNORECASE)
            extracted_time = match.group() if match else "12:00am"
            combined_str = f"{date_str} {extracted_time}"  # e.g., "1-5-2025 8:00pm"
            naive_datetime = datetime.strptime(combined_str, "%Y-%m-%d %I:%M%p")

            localized_datetime = base_configs["timezone"].localize(naive_datetime)
            return localized_datetime
        except Exception as e:
            raise ValueError(
                f"Error parsing datetime string: {date_str}  and time {time_str}: {e}"
            ) from e

    async def parse_base_html(
        self, soup: BeautifulSoup, date_str: str
    ) -> List[EventDTO]:
        """
        Parse HTML content to extract events.
        Main HTML parsing method that extracts event information from the page.
        Coordinates calls to venue and artist data scrapers to build complete event records.
        Can be extended to handle additional data sources by adding new parsing logic.

        Args:
            soup: BeautifulSoup object to parse
            date_str: Date string for the events

        Returns:
            List of EventDTO objects
        """
        try:
            events = []
            livewire_listing = soup.find("div", class_="livewire-listing")

            if not livewire_listing:
                logger.warning("No livewire-listing found on the page.")
                raise ScrapingError(
                    message="No events found for this date",
                    error_type=ErrorType.NO_EVENTS,
                    status_code=404,
                )

            for panel in livewire_listing.find_all("div", class_="panel panel-default"):
                # Venue name is each panel's title
                panel_title = panel.find("h3", class_="panel-title")
                # Extract venue info
                if panel_title is None:
                    logger.warning("Panel is missing Venue Name...This is unexpected.")
                # parse text to get venue name
                venue_name = (
                    panel_title.find("a").text.strip()
                    if panel_title
                    else "Unknown Venue"
                )

                logger.info(f"Processing venue: {venue_name}")
                # get wwoz's venue href from the venue name
                wwoz_venue_href = panel_title.find("a")["href"]
                # use href to get details, and return the original href in the venue data
                venue_data = await self.get_venue_data(wwoz_venue_href, venue_name)
                # find the panel's body to ensure we are only dealing with the correct rows
                panel_body = panel.find("div", class_="panel-body")

                for row in panel_body.find_all("div", class_="row"):
                    calendar_info = row.find("div", class_="calendar-info")
                    if not calendar_info:
                        continue
                    # the event link inner text is the artist name, not a link to the artists page though
                    # is the link to more event details ie related acts, which can be link to the artist, but not always
                    wwoz_event_link = calendar_info.find("a")
                    if not wwoz_event_link:
                        continue
                    # get artist name and wwoz event href
                    event_artist_name = wwoz_event_link.text.strip()
                    wwoz_event_href = wwoz_event_link["href"]
                    # use the href to for the event to scrape deeper for more details on artists, and return any
                    event_data, artist_data = await self.get_event_data(
                        wwoz_event_href,
                        event_artist_name,
                        datetime.strptime(date_str, "%Y-%m-%d").date(),
                    )
                    # Extract time string
                    time_str = calendar_info.find_all("p")[1].text.strip()
                    # the performance time had ought to be known
                    performance_time = (
                        self.parse_event_performance_time(date_str, time_str)
                        if time_str
                        else None
                    )

                    event = EventDTO(
                        artist_data=artist_data,
                        venue_data=venue_data,
                        event_data=event_data,
                        performance_time=performance_time,
                        scrape_time=datetime.now(base_configs["timezone"]).isoformat(),
                    )
                    events.append(event)

            return events
        except ScrapingError:
            raise
        except Exception as e:
            raise ScrapingError(
                message=f"Failed to parse webpage content: {e}",
                error_type=ErrorType.PARSE_ERROR,
                status_code=500,
            )

    async def close(self):
        """Clean up resources."""
        if self.session:
            await self.session.close()
