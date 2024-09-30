import os
import logging
import json
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from urllib.error import URLError
from datetime import datetime, date
import pytz

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define the timezone for New Orleans (CST/CDT)
NEW_ORLEANS_TZ = pytz.timezone("America/Chicago")

def get_url(base_url: str, date_str: str) -> str:
    return f"{base_url}?date={date_str}"


def fetch_html(url: str) -> str:
    try:
        with urlopen(Request(url)) as response:
            return response.read().decode("utf-8")
    except URLError as e:
        logger.error(f"Failed to fetch URL: {url}. Error: {e}")
        raise


def parse_html(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    livewire_listing = soup.find("div", class_="livewire-listing")
    if not livewire_listing:
        logger.warning("No livewire-listing found on the page.")
        return links

    for panel in livewire_listing.find_all("div", class_="panel panel-default"):
        for row in panel.find_all("div", class_="row"):
            artist_link = row.find("div", class_="calendar-info").find("a")
            if artist_link:
                links.append({artist_link.text.strip(): artist_link["href"]})
    return links


def scrape(base_url: str = None, date: date = None) -> list:
    base_url = base_url or os.getenv(
        "BASE_URL", "https://www.wwoz.org/calendar/livewire-music"
    )
    if date is None:
        # Get the current date in New Orleans timezone
        date = datetime.now(NEW_ORLEANS_TZ).date()
    date_format = os.getenv("DATE_FORMAT", "%Y-%m-%d")
    date_str = date.strftime(date_format)
    url = get_url(base_url, date_str)

    try:
        html = fetch_html(url)
        return parse_html(html)
    except Exception as e:
        logger.error(f"Error occurred during scraping: {e}")
        return []


def lambda_handler(event, context):
    # TODO implement error handling
    return scrape()
