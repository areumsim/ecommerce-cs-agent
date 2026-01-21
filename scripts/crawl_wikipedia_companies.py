import requests
from bs4 import BeautifulSoup

BASE = "https://en.wikipedia.org/wiki/"

def crawl_company(name: str) -> dict:
    url = BASE + name.replace(" ", "_")
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    info = {"name": name, "source": url}
    infobox = soup.find("table", {"class": "infobox"})
    if not infobox:
        return info
    for row in infobox.find_all("tr"):
        header = row.find("th")
        value = row.find("td")
        if header and value:
            info[header.text.strip()] = value.text.strip()
    return info

if __name__ == '__main__':
    print(crawl_company("Apple Inc."))
