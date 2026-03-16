from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import CITY_COUNCIL
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

import city_scrapers.spiders.losca_inglewood as losca_module

test_response = file_response(
    join(dirname(__file__), "files", "losca_inglewood.html"),
    url="https://www.cityofinglewood.org/AgendaCenter/UpdateCategoryList",
)
spider = losca_module.LoscaInglewoodCityCouncilSpider()

freezer = freeze_time("2026-03-10")
freezer.start()

parsed_items = [item for item in spider.parse(test_response)]

freezer.stop()


def test_title():
    assert parsed_items[3]["title"] == "Regular Meeting"


def test_title_special():
    special = [item for item in parsed_items if "Special" in item["title"]]
    assert all(item["title"] == "Special Meeting" for item in special)


def test_description():
    assert parsed_items[3]["description"] == ""


def test_start():
    assert parsed_items[3]["start"] == datetime(2026, 2, 24, 0, 0)


def test_end():
    assert parsed_items[3]["end"] is None


def test_time_notes():
    assert (
        parsed_items[3]["time_notes"]
        == "Please refer to the meeting attachment for more accurate start time"  # noqa
    )


def test_all_day():
    assert parsed_items[3]["all_day"] is False


def test_classification():
    assert parsed_items[3]["classification"] == CITY_COUNCIL


def test_location():
    assert parsed_items[3]["location"] == {
        "name": "Inglewood City Hall",
        "address": "One Manchester Blvd, Inglewood, CA 90301",
    }


def test_source():
    assert parsed_items[3]["source"] == (
        "https://www.cityofinglewood.org/AgendaCenter/Search/"
        "?term=&CIDs=3,&startDate=&endDate=&dateRange=&dateSelector="
    )


def test_links():
    assert parsed_items[3]["links"] == [
        {
            "href": "https://www.cityofinglewood.org/AgendaCenter/ViewFile/Agenda/_02242026-4463",  # noqa
            "title": "Agenda",
        }
    ]


def test_links_structure():
    # Every link must have href and title
    for item in parsed_items:
        for link in item["links"]:
            assert "href" in link
            assert "title" in link
            assert link["href"].startswith("https://")


def test_links_titles():
    # Link titles should only be known values
    valid_titles = {
        "Agenda",
        "Agenda (HTML)",
        "Agenda (PDF)",
        "Agenda Packet",
        "Minutes",
    }
    for item in parsed_items:
        for link in item["links"]:
            assert link["title"] in valid_titles


def test_no_duplicate_meetings():
    # No two meetings should share the same date + title
    seen = set()
    for item in parsed_items:
        key = (item["start"].date(), item["title"])
        assert key not in seen, f"Duplicate meeting found: {key}"
        seen.add(key)


def test_status():
    assert parsed_items[3]["status"] == "passed"


def test_cancelled_status():
    cancelled = [
        item for item in parsed_items if "cancelled" in item["title"].lower()
    ]  # noqa
    assert all(item["status"] == "cancelled" for item in cancelled)


def test_id():
    assert (
        parsed_items[3]["id"]
        == "losca_inglewood_city_council/202602240000/x/regular_meeting"
    )


@pytest.mark.parametrize("item", parsed_items)
def test_all_day_parametrize(item):
    assert item["all_day"] is False
