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


async def test_notion_query_event_parse():
    notion_client = AsyncClient(auth=notion_authentication_token)

    response_object = await notion_client.databases.query(
        notion_events_database_id,
        filter={
            "or": [{
                "property": "Status",
                "status": {
                    "equals": "Planning"
                }
            }, {
                "property": "Status",
                "status": {
                    "equals": "In progress"
                }
            }]
        })

    print("Event result:")
    for page in response_object["results"]:
        pprint.pprint(page["properties"]["Project name"]["title"][0]["plain_text"])
        pprint.pprint(page["properties"]["Event Date"]["date"])

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
