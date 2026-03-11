"""
Mixin for City of Inglewood AgendaCenter scrapers.
Fetches meetings by POSTing to UpdateCategoryList per year + category.
Requires fresh session via GET + CSRF token from /antiforgery endpoint.
"""

from city_scrapers_core.constants import NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider

import scrapy

from datetime import datetime

from dateutil.parser import parse as dateparse

import re


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
    location = {"name": "", "address": ""}

    #start_urls = ["https://www.cityofinglewood.org/AgendaCenter"]

    BASE_URL = "https://www.cityofinglewood.org"
    API_URL = BASE_URL + "/AgendaCenter/UpdateCategoryList"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    # REQUESTS
    # -------------------------

    def start_requests (self):
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
                dont_filter=True
                
            )


    def parse(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """

        for row in response.css("tr.catAgendaRow"):
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

            meeting = Meeting(
                title=self._parse_title(row),
                description="",
                classification=self._parse_classification(row),
                start=self._parse_start(row),
                end=None,
        #         all_day=self._parse_all_day(item),
        #         time_notes=self._parse_time_notes(item),
        #         location=self._parse_location(item),
        #         links=self._parse_links(item),
        #         source=self._parse_source(response),
             )

            meeting["status"] = self._get_status(meeting, raw_title)
            meeting["id"] = self._get_id(meeting)

            yield meeting

    def _parse_title(self, row):
        """Parse meeting title from agenda link text."""
        title = row.css("td:first-child p a::text").get(default="").strip().lower().replace("no meeting", "Cancelled")
        
        if "special" in title:
            return "Special Meeting"

        return "Regular Meeting"

    def _parse_description(self, item):
        """Parse or generate meeting description."""
        return ""

    def _parse_classification(self, item):
        """Parse or generate classification from allowed options."""
        return NOT_CLASSIFIED

    def _parse_start(self, row):
        """Parse date from aria-label on <strong> tag e.g. 'Agenda for March 10, 2026'"""
        agenda_attr = row.css("strong::attr(aria-label)").get(default="")
        date_str = agenda_attr.replace("Agenda for ", "").strip()
        start = dateparse(date_str)        
        return start

    def _parse_time_notes(self, item):
        """Parse any additional notes on the timing of the meeting"""
        return ""

    def _parse_all_day(self, item):
        """Parse or generate all-day status. Defaults to False."""
        return False

    def _parse_location(self, item):
        """Parse or generate location."""
        return {
            "address": "",
            "name": "",
        }

    def _parse_links(self, item):
        """Parse or generate links."""
        return [{"href": "", "title": ""}]

    def _parse_source(self, response):
        """Parse or generate source."""
        return response.url
