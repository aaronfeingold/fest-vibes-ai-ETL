import os
import logging
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def scrape():
    # Read base URL and date format from environment variables
    base_url = os.getenv("BASE_URL", "https://www.wwoz.org/calendar/livewire-music")

    date_format = os.getenv("DATE_FORMAT", "%Y-%m-%d")

    # Format the current date using the specified format
    date_str = datetime.now().date().strftime(date_format)

    # Build the full URL
    url = f"{base_url}?date={date_str}"

    html_page = urlopen(Request(url))
    soup = BeautifulSoup(html_page, "html.parser")

    links = []
    # Find the 'livewire-listing' class specifically
    livewire_listing = soup.find("div", class_="livewire-listing")
    # Find only the 'panel panel-default' divs within the 'livewire-listing' div
    if livewire_listing:
        panels = livewire_listing.find_all("div", class_="panel panel-default")
    else:
        logger.error("Error: No livewire-listing found on the page.")
        return []

    for panel in panels:
        for row in panel.find_all("div", class_="row"):
            artist_link = row.find("div", class_="calendar-info").find("a")
            if artist_link:
                links.append({artist_link.text.strip(): artist_link["href"]})

    return links


def lambda_handler(event, context):
    return scrape()
