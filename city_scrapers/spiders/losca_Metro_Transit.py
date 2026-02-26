import re
import unicodedata

from city_scrapers_core.constants import BOARD, CITY_COUNCIL, COMMITTEE, NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import LegistarSpider
from collections import defaultdict


class LoscaMetroTransitSpider(LegistarSpider):
    name = "losca_Metro_Transit"
    agency = "Los Angeles Metro Transit"
    timezone = "America/Los_Angeles"
    start_urls = ["https://metro.legistar.com/Calendar.aspx"]
    link_types = ["Meeting Details", "Audio"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    # Will add this later
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     # Can override since_year to start earlier
    #     self.since_year = 2015
    #     self._scraped_urls = set()

    def parse_legistar(self, events):
        for event in events:
            title = event.get("Name", {}).get("label", "No Title")

            if "test" in title.lower():
                continue
            
            start = self.legistar_start(event)
            if start:
                meeting_location, description = self._parse_location(event)
                meeting = Meeting(
                    title=self._clean_text(title),
                    description=self._clean_text(description),
                    classification=self._parse_classification(event),
                    start=start,
                    end=None,
                    all_day=False,
                    time_notes="",
                    location=meeting_location,
                    links=self.legistar_links(event),
                    source=self.legistar_source(event),
                )

                meeting["status"] = self._get_status(meeting)
                meeting["id"] = self._get_id(meeting)

            yield meeting

    def _parse_legistar_events(self, response):
        events_table = response.css("table.rgMasterTable")[0]

        headers = []
        for header in events_table.css("th[class^='rgHeader']"):
            header_text = (
                " ".join(header.css("*::text").extract()).replace("&nbsp;", " ").strip()
            )
            header_inputs = header.css("input")
            if header_text:
                headers.append(header_text)
            elif len(header_inputs) > 0:
                headers.append(header_inputs[0].attrib["value"])
            else:
                headers.append(header.css("img")[0].attrib["alt"])

        events = []
        for row in events_table.css("tr.rgRow, tr.rgAltRow"):
            try:
                data = defaultdict(lambda: None)
                for header, field in zip(headers, row.css("td")):
                    field_text = (
                        " ".join(field.css("*::text").extract())
                        .replace("&nbsp;", " ")
                        .strip()
                    )
                    url = None
                    if len(field.css("a")) > 0:
                        link_el = field.css("a")[0]
                        if "onclick" in link_el.attrib and link_el.attrib[
                            "onclick"
                        ].startswith(("radopen('", "window.open", "OpenTelerikWindow")):
                            url = response.urljoin(
                                link_el.attrib["onclick"].split("'")[1]
                            )
                        elif "href" in link_el.attrib:
                            url = response.urljoin(link_el.attrib["href"])
                    if url:
                        if "View.ashx?M=IC" in url:
                            header = "iCalendar"
                            value = {"url": url}
                        else:
                            value = {"label": field_text, "url": url}
                    else:
                        value = field_text

                    data[header] = value

                ical_url = data.get("iCalendar", {}).get("url")
                if ical_url is None or ical_url in self._scraped_urls:
                    continue
                else:
                    self._scraped_urls.add(ical_url)
                events.append(dict(data))
            except Exception:
                pass

        return events


    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        name_label = item.get("Name", {}).get("label", "").lower()
        if "committee" in name_label:
            return COMMITTEE
        if "board" in name_label:
            return BOARD
        if "council" in name_label:
            return CITY_COUNCIL
        return NOT_CLASSIFIED
    
    def _clean_text(self, text):
        """Normalize unicode characters in text (e.g. curly quotes, accented chars)."""
        if not text:
            return text
        # Normalize unicode to composed form (NFC), handles chars like ñ, é, etc.
        text = unicodedata.normalize("NFC", text)
        # Replace curly/smart apostrophes and quotes with standard ASCII equivalents
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        return text
    

    def _parse_location(self, item):
        """
        The location format of the meetings is not consistent.
        It is returned as a string or a dictionary. The string
        format at times contains the location/type of the held
        meeting. This function parses that and returns it as the
        meeting description.
        """
        location = {"name": "", "address": ""}
        description = ""
        meeting_location = ""
        if isinstance(item["Meeting Location"], dict):
            meeting_location = item["Meeting Location"]["label"]
            pattern = "Watch online:  https://boardagendas.metro.net"
            if pattern in meeting_location:
                splits = re.split(rf"({pattern})", meeting_location)
                address = splits[0]
                address = address.split("\r\n")
                address.insert(0, address.pop(-1))
                address = ",".join(address)
                location["address"] = address
                description = ", ".join(
                    [x.replace("\r", "").replace("\n", "").strip() for x in splits[1:]]
                )
                return location, description
        else:
            meeting_location = item["Meeting Location"]

        meeting_location = meeting_location.replace("(", "").replace(")", "").strip()
        splits = re.split(r"(\b\d{5}\b)", meeting_location)
        if len(splits) > 2:
            if "floor" in splits[2].lower() or "room" in splits[2].lower():
                room = splits[2].replace("\r\n", "").lstrip(", ").strip()
                address = f"{room}, {splits[0].strip()} {splits[1].strip()}"
                location["address"] = address
            else:
                address = f"{splits[0].strip()} {splits[1].strip()}"
                description = splits[2].strip()
                location["address"] = address

        return location, description
