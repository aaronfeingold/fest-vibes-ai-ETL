import re
from urllib.request import urlopen

def scrapeWWOZ():
  url = "https://www.wwoz.org/calendar/livewire-music"

  page = urlopen(url)

  html = page.read().decode("utf-8")

  matches = re.findall(r'<a[^>]* href="([^"]*)"', html)

  substring = 'events'
  base_url = "https://www.wwoz.org"
  links = []
  for match in matches:
    if substring in match:
      link = base_url + match
      links.append(link)

  return links


print(scrapeWWOZ())








