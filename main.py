import os
import logging
import json
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime, date
import pytz
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define the timezone for New Orleans (CST/CDT)
NEW_ORLEANS_TZ = pytz.timezone("America/Chicago")

# Default headers for HTTP requests to prevent Bot detection
DEFAULT_HEADERS = {
    "User-Agent": os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def ScrapingError(Exception):
    pass


def get_url(base_url: str, date_str: str) -> str:
    return f"{base_url}?date={date_str}"


def fetch_html(url: str) -> str:
    try:
        req = Request(url, headers=DEFAULT_HEADERS)
        with urlopen(req) as response:
            return response.read().decode("utf-8")
    except URLError as e:
        logger.error(f"Failed to fetch URL: {url}. Error: {e}")
        raise
    except HTTPError as e:
        logger.error(f"HTTP Error: {e.code} - {e.reason} for URL: {url}")
        raise ScrapingError(f"Failed to fetch data: HTTP {e.code}")


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


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # Configure as needed for your frontend
        },
        "body": json.dumps(body),
    }


def scrape(base_url: str = None, date: date = None) -> list:
    base_url = base_url or os.getenv(
        "BASE_URL", "https://www.wwoz.org/calendar/livewire-music"
    )
    date = date or datetime.now(NEW_ORLEANS_TZ).date()
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
    events = scrape()
    return create_response(200, {"status": "success", "data": events})
