from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from datetime import datetime


def scrape_wwoz(event, context):
    url = f"https://www.wwoz.org/calendar/livewire-music?date={datetime.now().date().strftime('%Y-%m-%d')}"
    html_page = urlopen(Request(url))
    soup = BeautifulSoup(html_page, "html.parser")

    links = []
    # Find the 'livewire-listing' class specifically
    livewire_listing = soup.find("div", class_="livewire-listing")
    # Find only the 'panel panel-default' divs within the 'livewire-listing' div
    if livewire_listing:
        panels = livewire_listing.find_all("div", class_="panel panel-default")
    else:
        print("Error: No livewire-listing found on the page.")
        return []

    for panel in panels:
        for row in panel.find_all("div", class_="row"):
            artist_link = row.find("div", class_="calendar-info").find("a")

            links.append({artist_link.text.strip(): artist_link["href"]})

    return links
