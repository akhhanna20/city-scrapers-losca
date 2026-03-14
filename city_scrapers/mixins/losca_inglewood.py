"""
Mixin for City of Inglewood AgendaCenter scrapers.
Fetches meetings by POSTing to UpdateCategoryList per year + category.
"""

from collections import defaultdict
from datetime import datetime

import scrapy
from city_scrapers_core.constants import BOARD, CITY_COUNCIL, COMMISSION, NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.parser import parse as dateparse


class LoscaInglewoodMixinMeta(type):
    """
    Metaclass that enforces required static variables.
    """

    def __init__(cls, name, bases, dct):
        required_static_vars = ["name", "agency", "cat_id"]
        missing = [v for v in required_static_vars if v not in dct]
        if missing:
            raise NotImplementedError(f"{name} must define: {', '.join(missing)}")
        super().__init__(name, bases, dct)


class LoscaInglewoodMixin(CityScrapersSpider, metaclass=LoscaInglewoodMixinMeta):
    """
    Required class attributes:
    - name:    Scrapy spider name
    - agency:  Agency display name
    - cat_id:  AgendaCenter category ID (e.g. 3 for City Council)
    """

    name = None
    agency = None
    cat_id = None
    start_year = None
    time_notes = "See agenda for meeting time"
    timezone = "America/Los_Angeles"

    BASE_URL = "https://www.cityofinglewood.org"
    API_URL = BASE_URL + "/AgendaCenter/UpdateCategoryList"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    # REQUESTS
    # -------------------------

    def start_requests(self):
        current_year = datetime.now().year
        for year in range(self.start_year, current_year + 2):
            yield scrapy.FormRequest(
                url=self.API_URL,
                method="POST",
                formdata={
                    "year": str(year),
                    "catID": str(self.cat_id),
                    "startDate": "",
                    "endDate": "",
                    "term": "",
                    "preVersionScreening": "false",
                },
                headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                },
                callback=self.parse,
                dont_filter=True,
            )

    def parse(self, response):
        """
        Parse meetings with this deduplication strategy:
        1. If Spanish and non-Spanish rows exist for the same date → keep non-Spanish.
        2. If exact title duplicates remain after step 1 → keep first seen.
        """

        # 1. For deduplication to pick to keep non-Spanish over Spanish
        rows_by_date = defaultdict(list)

        for row in response.css("tr.catAgendaRow"):
            # print ("ROW", row)
            start = self._parse_start(row)
            if not start:
                continue

            raw_title = (
                row.css("td:first-child p a::text")
                .get(default="")
                .lower()
                .strip()
                .replace("no meeting", "cancelled")
                .replace("canceled", "cancelled")
            )
            rows_by_date[start.date()].append((start, raw_title, row))

        # 2. Now we can deduplicate
        for _, entries in rows_by_date.items():
            # Prefere non-spanish over spanish, fall back to all if only Spanish exists
            non_spanish = [(s, t, r) for s, t, r in entries if "spanish" not in t]
            chosen_meeting = non_spanish or entries

            # Among duplicates with same title, keep row with most attachments/first seen  # noqa
            best_by_title = {}
            for start, raw_title, row in chosen_meeting:
                title = self._parse_title(row)
                links = self._parse_links(row)
                if title not in best_by_title or len(links) > len(
                    best_by_title[title][2]
                ):
                    best_by_title[title] = (start, raw_title, links)

            for title, (start, raw_title, links) in best_by_title.items():
                meeting = Meeting(
                    title=title,
                    description="",
                    classification=self._parse_classification(row),
                    start=start,
                    end=None,
                    all_day=False,
                    time_notes=self.time_notes,
                    location=self.location,
                    links=links,
                    source=self._parse_source(),
                )

                meeting["status"] = self._get_status(meeting, raw_title)
                meeting["id"] = self._get_id(meeting)

                yield meeting

    def _parse_title(self, row):
        """Parse meeting title from agenda link text."""
        title = row.css("td:first-child p a::text").get(default="").strip().lower()

        meeting_type = "Special Meeting" if "special" in title else "Regular Meeting"

        has_english = "english" in title
        has_spanish = "spanish" in title

        if has_english and has_spanish:
            return f"{meeting_type} (English/Spanish)"
        if has_spanish:
            return f"{meeting_type} (Spanish)"
        if has_english:
            return f"{meeting_type} (English)"

        return meeting_type

    def _parse_classification(self, item):
        """Parse classification from agency name."""
        agency_lower = self.agency.lower()
        if "council" in agency_lower:
            return CITY_COUNCIL
        if "board" in agency_lower:
            return BOARD
        if "commission" in agency_lower:
            return COMMISSION
        return NOT_CLASSIFIED

    def _parse_start(self, row):
        agenda_attr = row.css("strong::attr(aria-label)").get(default="")
        date_str = agenda_attr.replace("Agenda for ", "").strip()
        start = dateparse(date_str)
        return start

    def _parse_location(self, item):
        """Parse or generate location."""
        return {
            "address": "",
            "name": "",
        }

    def _parse_links(self, row):
        """Extract all document links from the download popout menu."""
        links = []
        seen = set()
        for a in row.css("ol[role='menu'] a[href]"):
            href = a.attrib.get("href", "").strip()
            if not href or href in seen:
                continue
            if not href.startswith("http"):
                href = self.BASE_URL + href
            title = a.css("::text").get(default="").strip()
            title_lower = title.lower()

            if "previous version" in title_lower.lower():
                continue
            if "packet" in title_lower:
                title = "Agenda Packet"
            elif "html" in title_lower:
                title = "Agenda (HTML)"
            elif "pdf" in title_lower:
                title = "Agenda (PDF)"
            else:
                title = "Agenda"

            links.append({"href": href, "title": title})
            seen.add(href)

        # Minutes link from the separate td.minutes cell
        minutes_href = row.css("td.minutes a::attr(href)").get(default="").strip()
        if minutes_href and minutes_href not in seen:
            if not minutes_href.startswith("http"):
                minutes_href = self.BASE_URL + minutes_href
            links.append({"href": minutes_href, "title": "Minutes"})

        return links

    def _parse_source(self):
        """Parse or generate source."""
        source_url = f"{self.BASE_URL}/AgendaCenter/Search/?term=&CIDs={self.cat_id},&startDate=&endDate=&dateRange=&dateSelector="  # noqa
        return source_url
