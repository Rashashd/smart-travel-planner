import httpx

DESTINATIONS = [
    'Paris', 'Tokyo', 'Bali', 'Reykjavík', 'Marrakech', 'Cuzco', 'Lisbon', 'Bangkok', 'Barcelona', 'Queenstown', 'Santorini', 'Beirut', 'Dubai', 'Istanbul'
]


async def fetch_wikivoyage(client: httpx.AsyncClient, destination: str) -> str:
    # MediaWiki Action API — more stable than rest_v1/mobile-sections (retired)
    # explaintext=1 returns plain text so no HTML stripping needed
    url = "https://en.wikivoyage.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "titles": destination,
        "format": "json",
        "explaintext": "1",
        "exsectionformat": "plain",
    }
    headers = {"User-Agent": "smart-travel-planner/1.0 (racha.chamseddine96@gmail.com)"}
    response = await client.get(url, params=params, timeout=15.0, headers=headers)
    response.raise_for_status()
    data = response.json()

    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))
    return page.get("extract", "")
