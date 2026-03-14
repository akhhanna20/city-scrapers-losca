"""
This file dynamically creates spider classes for the spider factory
mixin that agencies use.
"""

from city_scrapers.mixins.losca_inglewood import LoscaInglewoodMixin

spider_configs = [
    {
        "class_name": "LoscaInglewoodCityCouncilSpider",
        "name": "losca_inglewood_city_council",
        "agency": "City of Inglewood - City Council",
        "cat_id": 3,
        "start_year": 2023,
        "time_notes": "See agenda for meeting time",
        "location": {
            "name": "Inglewood City Hall",
            "address": "One Manchester Blvd, Inglewood, CA 90301",
        },
    },
    {
        "class_name": "LoscaInglewoodArtsCommissionSpider",
        "name": "losca_inglewood_arts_commission",
        "agency": "City of Inglewood - Arts Commission",
        "cat_id": 6,
        "start_year": 2023,
        "time_notes": "See agenda for meeting time",
        "location": {
            "name": "Inglewood City Hall",
            "address": "One Manchester Blvd, Inglewood, CA 90301",
        },
    },
    {
        "class_name": "LoscaInglewoodLibraryBoardSpider",
        "name": "losca_inglewood_library_board",
        "agency": "City of Inglewood - Library Board",
        "cat_id": 5,
        "start_year": 2023,
        "time_notes": "See agenda for meeting time",
        "location": {
            "name": "Inglewood City Hall",
            "address": "One Manchester Blvd, Inglewood, CA 90301",
        },
    },
    {
        "class_name": "LoscaInglewoodParkRecreationCommissionSpider",
        "name": "losca_inglewood_park_recreation_commission",
        "agency": "City of Inglewood - Park & Recreation Commission",
        "cat_id": 7,
        "start_year": 2023,
        "time_notes": "See agenda for meeting time",
        "location": {
            "name": "Inglewood City Hall",
            "address": "One Manchester Blvd, Inglewood, CA 90301",
        },
    },
]


def create_spiders():
    """
    Dynamically create spider classes using the spider_configs list
    and register them in the global namespace.
    """
    for config in spider_configs:
        class_name = config["class_name"]

        if class_name not in globals():
            # Build attributes dict without class_name to avoid duplication.
            # We make sure that the class_name is not already in the global namespace
            # Because some scrapy CLI commands like `scrapy list` will inadvertently
            # declare the spider class more than once otherwise
            attrs = {k: v for k, v in config.items() if k != "class_name"}

            # Dynamically create the spider class
            spider_class = type(
                class_name,
                (LoscaInglewoodMixin,),
                attrs,
            )

            globals()[class_name] = spider_class


# Create all spider classes at module load
create_spiders()
