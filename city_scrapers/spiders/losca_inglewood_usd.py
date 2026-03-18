import html
import json
import re
from datetime import datetime

import requests
import scrapy
from city_scrapers_core.constants import BOARD, NOT_CLASSIFIED
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from curl_cffi import requests as curl_requests
from dateutil.parser import ParserError
from dateutil.parser import parse as dateparse
from parsel import Selector


class LoscaInglewoodUsdSpider(CityScrapersSpider):
    name = "losca_inglewood_usd"
    agency = "Inglewood Unified School District"
    timezone = "America/Los_Angeles"

    main_url = "https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=36030265"
    api_url = "https://simbli.eboardsolutions.com/Services/api/GetMeetingListing"
    video_url = "https://www.inglewoodusd.com/apps/pages/index.jsp?uREC_ID=1471610&type=d&pREC_ID=1753679"
    school_id = "36030265"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._video_links_by_date = {}

    def start_requests(self):
        """
        Fetch main page with curl_cffi to bypass fingerprinting, extract tokens.
        curl_cffi with impersonate="chrome120" mimics Chrome's TLS fingerprint at a low level.
        It bypasses it and gets the real page with the tokens embedded in the HTML.
        """
        self._video_links_by_date = self._fetch_video_links()

        response = curl_requests.get(
            self.main_url,
            impersonate="chrome120",
        )

        if not response or len(response.text) < 10000:
            self.logger.warning(
                f"Unexpected response from {self.main_url}: "
                f"status={response.status_code}, length={len(response.text)}"
            )
            return

        connection_string = self._extract_token(
            response.text,
            [r"var\s+constr\s*=\s*'([^']+)'", r'var\s+constr\s*=\s*"([^"]+)"'],
        )

        security_token = self._extract_token(
            response.text,
            [
                r"var\s+sToken\s*=\s*'([^']+)'",
                r'var\s+sToken\s*=\s*"([^"]+)"',
                r'"SecurityToken"\s*:\s*"([^"]+)"',
            ],
        )

        if connection_string and security_token:
            
            yield from self._fetch_main_meetings_page(0, connection_string, security_token)

    def _fetch_video_links(self):
        """Fetch video links from the regular webpage."""
        response = requests.get(self.video_url)
        if not response or response.status_code != 200:
            self.logger.warning(
                f"Failed to fetch video links from {self.video_url}: "
                f"status={response.status_code}, length={len(response.text)}"
            )
            return {}
        
        selector_parsel = Selector(text=response.text)
        videos_by_date = {}

        for section in selector_parsel.css(".collapsible-content"):
            for div in section.css("div"):
                text = div.css("::text").get(default="").strip()
                href = div.css("a::attr(href)").get()
 
                # Skip empty divs and divs that are just links
                if not text or text == "\xa0" or href:
                    continue
 
                # Try to parse date from text e.g. "Regular Board Meeting, January 14, 2026"
                try:
                    date = dateparse(text, fuzzy=True).date()
                except (ParserError, ValueError, OverflowError):
                    continue
 
                # Get the next sibling div that contains a link
                next_href = div.xpath(
                    "following-sibling::div[.//a][1]//@href"
                ).get()
 
                if next_href and date:
                    videos_by_date[date] = {"href": next_href, "title": "Video"}
 
        return videos_by_date
        

    def _extract_token(self, html_text, patterns):
        """Extract token from HTML using regex patterns."""
        for pattern in patterns:
            match = re.search(pattern, html_text)
            if match:
                return match.group(1)
        return None

    def _fetch_main_meetings_page(self, record_start, connection_string, security_token):
        """Fetch a page of meetings via API with pagination (50 per page)."""
        payload = {
            "ListingType": "0",
            "TimeZone": "-60",
            "CustomSort": 0,
            "SortColName": "DateTime",
            "IsSortDesc": True,
            "RecordStart": record_start,
            "RecordCount": 50,
            "ParentGroup": None,
            "IsUserLoggedIn": False,
            "UserID": "",
            "UserRole": None,
            "EncUserId": None,
            "Id": 0,
            "SchoolID": self.school_id,
            "ConnectionString": connection_string,
            "SecurityToken": security_token,
            "CreatedOn": "0001-01-01T00:00:00",
            "CreatedBy": None,
            "ModifiedOn": "0001-01-01T00:00:00",
            "ModifiedBy": None,
            "DeletedBy": None,
            "DeletedOnUTC": None,
            "IsDeleted": False,
            "FilterExp": "ML_TypeTitle in ('Board Meeting') "
        }

        yield scrapy.Request(
            url=self.api_url,
            method="POST",
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.main_url,
            },
            body=json.dumps(payload),
            callback=self.parse,
            meta={
                "record_start": record_start,
                "connection_string": connection_string,
                "security_token": security_token,
            },
        )

    def parse(self, response):
        """Parse API response and handle pagination."""
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.warning(
                f"Failed to parse JSON response from {response.url}: {response.text[:200]}"
            )
            return

        meetings = self._extract_meetings_from_response(data)
        if not meetings:
            return

        for meeting_data in meetings:
            meeting = self._parse_meeting(meeting_data)
            if meeting:
                yield meeting

        # Paginate if full page returned
        if len(meetings) > 0:
            try:
                record_start = response.meta.get("record_start", 0)
                connection_string = response.meta["connection_string"]
                security_token = response.meta["security_token"]
            except AttributeError:
                self.logger.warning(
                    "response.meta not available, skipping pagination"
                )
                return
            
            next_offset = record_start + len(meetings)
            yield from self._fetch_main_meetings_page(
                next_offset,
                connection_string,
                security_token,
            )

    def _parse_meeting(self, meeting_data):
        """Convert raw Simbli meeting data into a Meeting object."""
        start = self._parse_start_time(meeting_data)
        if not start:
            return None

        meeting_id = meeting_data.get("Master_MeetingID")
        meeting_url = f"https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S={self.school_id}&MID={meeting_id}"

        raw_title = meeting_data.get("MM_MeetingTitle", "Board Meeting")
        links = [{"href": meeting_url, "title": "Meeting Details"}]

        # Attach video link if one exists for this date
        video = self._video_links_by_date.get(start.date())
        if video:
            links.append(video)

        meeting = Meeting(
            title=self._normalize_title(raw_title),
            description="",
            classification=self._parse_classification(raw_title),
            start=start,
            end=None,
            all_day=False,
            time_notes="Please refer to the meeting attachments for more accurate information about the meeting location and time.",
            location=self._parse_location(meeting_data),
            links=links,
            source=self.main_url,
        )

        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)

        return meeting

    def _normalize_title(self, title):
        """Remove date patterns and clean up meeting titles."""
        title = html.unescape(title)

        date_patterns = [
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\s+",  # noqa
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s+",  # noqa
            r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s+",  # noqa
        ]
        for pattern in date_patterns:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE)

        title = re.sub(
            r"\(\s*(cancel\w+|rescheduled)\s*\)", r"\1", title, flags=re.IGNORECASE
        )

        return " ".join(title.split()).strip()

    def _parse_classification(self, title):
        """Classify meeting based on title keywords."""
        title_lower = title.lower()
        if "board" in title_lower:
            return BOARD
        return NOT_CLASSIFIED

    def _parse_start_time(self, meeting_data):
        """Parse meeting start time from various formats."""
        date_str = meeting_data.get("DateTime") or meeting_data.get("MM_DateTime")
        if not date_str:
            return None

        for fmt in ["%m/%d/%Y - %I:%M %p", "%Y-%m-%dT%H:%M:%S"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _parse_location(self, meeting_data):
        """Parse meeting location from Simbli data."""
        address1 = (meeting_data.get("MM_Address1") or "").strip()
        address2 = (meeting_data.get("MM_Address2") or "").strip()
        address3 = (meeting_data.get("MM_Address3") or "").strip()

        location_address = " ".join(filter(None, [address2, address3])).strip()

        return {
            "name": address1,
            "address": location_address,
        }

    def _extract_meetings_from_response(self, data):
        """Extract meetings list from various JSON response structures."""
        if isinstance(data, dict):
            return (
                data.get("MeetingList")
                or data.get("Data")
                or data.get("data")
                or data.get("meetings")
            )
        if isinstance(data, list):
            return data
        return None