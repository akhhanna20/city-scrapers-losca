from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD, PASSED
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.losca_inglewood_usd import LoscaInglewoodUsdSpider

test_response = file_response(
    join(dirname(__file__), "files", "losca_inglewood_usd.json"),
    url="https://simbli.eboardsolutions.com/Services/api/GetMeetingListing",
)


@pytest.fixture
def spider():
    s = LoscaInglewoodUsdSpider()
    s._video_links_by_date = {
        datetime(2026, 3, 11).date(): {
            "href": "https://www.youtube.com/live/rckdkcEcGag",
            "title": "Video",
        }
    }
    return s


@pytest.fixture
def parsed_items(spider):
    with freeze_time("2026-03-17"):
        return [item for item in spider.parse(test_response)]


def test_count(parsed_items):
    assert len(parsed_items) == 49


def test_title(parsed_items):
    assert parsed_items[0]["title"] == "Regular Board Meeting"


def test_description(parsed_items):
    assert parsed_items[0]["description"] == ""


def test_start(parsed_items):
    assert parsed_items[0]["start"] == datetime(2026, 3, 11, 17, 0)


def test_end(parsed_items):
    assert parsed_items[0]["end"] is None


def test_time_notes(parsed_items):
    assert parsed_items[0]["time_notes"] == (
        "Please refer to the meeting attachments for more accurate "
        "information about the meeting location and time."
    )


def test_id(parsed_items):
    assert (
        parsed_items[0]["id"]
        == "losca_inglewood_usd/202603111700/x/regular_board_meeting"
    )  # noqa


def test_status(parsed_items):
    assert parsed_items[0]["status"] == PASSED


def test_classification(parsed_items):
    assert parsed_items[0]["classification"] == BOARD


def test_location(parsed_items):
    assert parsed_items[0]["location"] == {
        "name": "Dr. Ernest Shaw Board Room",
        "address": "401 S. Inglewood Avenue Inglewood, CA 90301",
    }


def test_session_time_notes(parsed_items):
    # Meeting with session times in address1
    session_item = next(
        item for item in parsed_items if item["start"] == datetime(2026, 1, 28, 17, 0)
    )
    assert (
        session_item["time_notes"] == "CLOSED SESSION 5:00p.m. / PUBLIC SESSION 5:30p.m"
    )


def test_session_location(parsed_items):
    session_item = next(
        item for item in parsed_items if item["start"] == datetime(2026, 1, 28, 17, 0)
    )
    assert session_item["location"] == {
        "name": "Dr. Ernest Shaw Board Room",
        "address": "401 S. Inglewood Avenue Inglewood, CA 90301",
    }


def test_links_with_video(parsed_items):
    assert parsed_items[0]["links"] == [
        {
            "href": "https://simbli.eboardsolutions.com/SB_Meetings/ViewMeeting.aspx?S=36030265&MID=50957",  # noqa
            "title": "Meeting Details",
        },
        {"href": "https://www.youtube.com/live/rckdkcEcGag", "title": "Video"},
    ]


def test_links_no_video(parsed_items):
    assert len(parsed_items[1]["links"]) == 1
    assert parsed_items[1]["links"][0]["title"] == "Meeting Details"


def test_source(parsed_items):
    assert (
        parsed_items[0]["source"]
        == "https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=36030265"  # noqa
    )


def test_all_day(parsed_items):
    assert parsed_items[0]["all_day"] is False
