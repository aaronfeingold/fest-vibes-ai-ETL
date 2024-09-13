import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_wwoz(date):
    url = f"https://www.wwoz.org/calendar/livewire-music?date={date}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    links = []
    # Find the 'livewire-listing' class specifically
    livewire_listing = soup.find("div", class_="livewire-listing")
    # Find only the 'panel panel-default' divs within the 'livewire-listing' div
    if livewire_listing:
        panels = livewire_listing.find_all('div', class_='panel panel-default')
    else:
        print("Error: No livewire-listing found on the page.")
        return []

    for panel in panels:
        for row in panel.find_all('div', class_='row'):
            artist_link = row.find("div", class_="calendar-info").find("a")

            links.append({artist_link.text.strip(): artist_link["href"]})

    return links


def main(event, context):
    today = datetime.now().date()
    lw_events = scrape_wwoz(today.strftime('%Y-%m-%d'))
    print(lw_events)

    # Save to a JSON file
    with open('events.json', 'w') as f:
        json.dump(lw_events, f)

if __name__ == "__main__":
    main(None, None)
