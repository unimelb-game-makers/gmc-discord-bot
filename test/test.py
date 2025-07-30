# Test module, defines tests

import logging
from notion_client import AsyncClient
from bot.config import notion_authentication_token, notion_events_database_id, notion_tasks_database_id
import pprint


async def test_notion_available_pages():
    notion_client = AsyncClient(auth=notion_authentication_token)

    query = await notion_client.search(filter={
        "property": "object",
        "value": "page"
    })

    print("Printing all available pages for the notion client:")
    pprint.pprint(query["results"])


async def test_notion_retrieve_event_database():
    notion_client = AsyncClient(auth=notion_authentication_token)

    response_object = await notion_client.databases.retrieve(
        notion_events_database_id)

    print("Printing the event database:")
    pprint.pprint(response_object)


async def test_notion_query_event_database():
    notion_client = AsyncClient(auth=notion_authentication_token)

    response_object = await notion_client.databases.query(
        notion_events_database_id)

    print("Printing the event database:")
    pprint.pprint(response_object)

# Notes:
# Filtered by Public Checkbox
# Public Name MUST BE NON-BLANK
# Event Date MUST BE NON-BLANK and use the correct dates in AEST
# Public Description, Venue and Thumbnail are synced in a best-effort manner
# Key names and types are HARDCODED, so please inform any changes!!

# For discord events:
# 1. You can't schedule events in the past
# 2. Location string must be 100 or fewer characters in length
async def test_notion_query_event_parse():
    notion_client = AsyncClient(auth=notion_authentication_token)

    response_object = await notion_client.databases.query(
        notion_events_database_id,
        filter={
            "property": "Public Checkbox",
            "checkbox": {
                "equals": True
            }
        })

    print("Event result:")
    for page in response_object["results"]:
        pprint.pprint(page["properties"]["Public Name"]["rich_text"][0]["plain_text"])
        pprint.pprint(page["properties"]["Event Date"]["date"])
        pprint.pprint(page["properties"]["Public Description"]["rich_text"])
        pprint.pprint(page["properties"]["Venue"]["rich_text"])
        pprint.pprint(page["properties"]["Thumbnail"])

async def test_notion_query_task_parse():
    notion_client = AsyncClient(auth=notion_authentication_token)

    response_object = await notion_client.databases.query(
        notion_tasks_database_id,
        filter={
            "property": "Status",
            "status": {
                "equals": "In progress"
            }
        })

    print("Task result:")
    for page in response_object["results"]:
        pprint.pprint(page)
