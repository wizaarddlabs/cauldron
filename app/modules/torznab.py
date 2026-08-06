import httpx
import xml.etree.ElementTree as ET
import re

from app.models import TorrentResult


class TorznabClient:

    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key


    def search(self, query: str):

        params = {
            "apikey": self.api_key,
            "t": "search",
            "q": query
        }

        with httpx.Client(timeout=60) as client:
            response = client.get(
                self.url,
                params=params
            )

        response.raise_for_status()

        return self.parse(response.text)


    def parse(self, xml: str):

        root = ET.fromstring(xml)

        results = []

        for item in root.findall(".//item"):

            title = item.findtext("title")

            if not title:
                continue


            magnet = None
            info_hash = None
            size = None
            seeders = None


            # enclosure usually contains magnet
            enclosure = item.find("enclosure")

            if enclosure is not None:
                magnet = enclosure.attrib.get("url")


            # Torznab attributes
            for attr in item.findall(".//{http://torznab.com/schemas/2015/feed}attr"):

                name = attr.attrib.get("name")
                value = attr.attrib.get("value")


                if name == "size":
                    try:
                        size = int(value)
                    except:
                        pass


                elif name == "seeders":
                    try:
                        seeders = int(value)
                    except:
                        pass


                elif name == "infohash":
                    info_hash = value


            # Extract infohash from magnet if needed
            if not info_hash and magnet:

                match = re.search(
                    r"btih:([a-fA-F0-9]{40})",
                    magnet
                )

                if match:
                    info_hash = match.group(1)


            # Skip unusable torrents
            if not magnet:
                continue


            results.append(
                TorrentResult(
                    title=title,
                    info_hash=info_hash or "",
                    magnet=magnet,
                    size_bytes=size,
                    seeders=seeders,
                    source="jackett",
                    indexer="jackett"
                )
            )


        return results