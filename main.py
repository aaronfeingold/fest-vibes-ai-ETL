import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_wwoz(date):
    url = f"https://www.wwoz.org/calendar/livewire-music?date={date}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    events = []
    # Find the 'livewire-listing' class specifically
    livewire_listing = soup.find('div', class_='livewire-listing')

    # Find only the 'panel panel-default' divs within the 'livewire-listing' div

    if livewire_listing:
        panels = livewire_listing.find_all('div', class_='panel panel-default')
    else:
        print("Error: No livewire-listing found on the page.")
        return []

    for panel in panels:
        venue_name = panel.find('h3', class_='panel-title').text.strip()
        venue_url = panel.find('h3', class_='panel-title').find('a')['href']

        for row in panel.find_all('div', class_='row'):
            event = {}
            event['venue_name'] = venue_name
            event['venue_url'] = venue_url

            date_info = row.find('div', class_='col-xs-2 calendar-page')
            month = date_info.find('div', class_='month').text.strip()
            day = date_info.find('div', class_='day').text.strip()

            event_info = row.find('div', class_='col-xs-10 calendar-info')
            artist_link = event_info.find('a')
            event['artist_name'] = artist_link.text.strip()
            event['event_url'] = artist_link['href']

            date_time = event_info.find_all('p')[1].text.strip()
            date_time = f"{month} {day} {date_time.split('at')[1].strip()}"
            event['performance_time'] = datetime.strptime(date_time, "%b %d %I:%M%p")

            events.append(event)

    return events


def main(event, context):
    today = datetime.now().date()
    lw_events = scrape_wwoz(today.strftime('%Y-%m-%d'))
    print(lw_events)
    for lwe in lw_events:
        lwe['performance_time'] = lwe['performance_time'].isoformat()

    # Save to a JSON file
    with open('events.json', 'w') as f:
        json.dump(lw_events, f)

if __name__ == "__main__":
    main(None, None)
