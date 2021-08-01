from bs4 import BeautifulSoup
from urllib.request import Request, urlopen

def scraper(event, context):
  url = "https://www.wwoz.org/calendar/livewire-music"

  html_page = urlopen(Request(url))

  soup = BeautifulSoup(html_page, features="html.parser")

  links = []

  for link in soup.find_all('a'):
    alike = "/events/"
    event_href = str(link.get('href'))
    artist_name  = str(link.renderContents()).replace("b'\\n", "").replace("'", "").strip()
    artist_event = {}

    if alike in event_href:
      artist_event[artist_name] = event_href
      links.append(artist_event)

  return links




