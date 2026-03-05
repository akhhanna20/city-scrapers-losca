import json
from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD, COMMITTEE
from freezegun import freeze_time

from city_scrapers.spiders.losca_Metro_Transit import LoscaMetroTransitSpider

freezer = freeze_time("2026-03-05")
freezer.start()

with open(
    join(dirname(__file__), "files", "losca_Metro_Transit.json"), "r", encoding="utf-8"
) as f:
    test_response = json.load(f)

spider = LoscaMetroTransitSpider()
parsed_items = [item for item in spider.parse_legistar(test_response)]

freezer.stop()


def test_count():
    assert len(parsed_items) == 65


def test_title():
    assert (
        parsed_items[37]["title"]
        == "Measure M Independent Taxpayer Oversight Committee"
    )


def test_description():
    assert (
        parsed_items[37]["description"]
        == "Watch online:  https://boardagendas.metro.net, Listen by phone: Dial 888-978-8818 and enter Access Code:5647249# (English) or 7292892# (Español)To give written or live public comment, please see the top of page 4"  # noqa
    )


def test_start():
    assert parsed_items[37]["start"] == datetime(2026, 3, 4, 10, 0)


def test_end():
    assert parsed_items[37]["end"] is None


def test_time_notes():
    assert parsed_items[37]["time_notes"] == ""


def test_id():
    assert (
        parsed_items[37]["id"]
        == "losca_Metro_Transit/202603041000/x/measure_m_independent_taxpayer_oversight_committee"  # noqa
    )


def test_status():
    assert parsed_items[37]["status"] == "passed"


def test_location():
    assert parsed_items[37]["location"] == {
        "name": "",
        "address": "3rd Floor, Metro Board Room ,One Gateway Plaza, Los Angeles, CA 90012, ",  # noqa
    }


def test_source():
    assert (
        parsed_items[37]["source"]
        == "https://metro.legistar.com/DepartmentDetail.aspx?ID=41000&GUID=88D5BF86-70AA-42B9-B7F5-AF9785959903"  # noqa
    )


def test_links():
    assert parsed_items[37]["links"] == [
        {
            "href": "https://metro.legistar.com/View.ashx?M=A&ID=1371499&GUID=76F1ECE2-63B6-42CB-BAF2-835C73669277",  # noqa
            "title": "Agenda",
        },
        {
            "href": "https://metro.legistar.com/MeetingDetail.aspx?ID=1371499&GUID=76F1ECE2-63B6-42CB-BAF2-835C73669277&Options=info|&Search=",  # noqa
            "title": "Meeting Details",
        },
        {
            "href": "https://metro.legistar.com/Video.aspx?Mode=Granicus&ID1=3960&Mode2=Video", # noqa
            "title": "Audio",
        },
    ]


def test_classification():
    assert parsed_items[0]["classification"] == BOARD
    assert parsed_items[2]["classification"] == COMMITTEE
    assert parsed_items[37]["classification"] == COMMITTEE


@pytest.mark.parametrize("item", parsed_items)
def test_all_day(item):
    assert item["all_day"] is False
