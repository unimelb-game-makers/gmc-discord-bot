# Test module, defines tests

import logging
from notion_client import AsyncClient
from bot.config import notion_authentication_token, notion_events_database_id, \
    notion_tasks_database_id, notion_people_database_id
import pprint
import requests

async def test_notion_available_databases():
    headers = {
        "Authorization": f"Bearer {notion_authentication_token}",
        "Notion-Version": "2022-06-28",  # Latest stable version
        "Content-Type": "application/json",
    }
    url = "https://api.notion.com/v1/search"
    payload = {
        "filter": {
            "property": "object",
            "value": "database"
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        databases = data.get("results", [])
        print("Databases accessible by this integration:\n")
        for db in databases:
            name = db["title"][0]["plain_text"] if db["title"] else "(untitled)"
            print(f"- {name}")
            pprint.pprint(db)
    else:
        print("Error:", response.status_code, response.text)

async def test_notion_query_task_parse():
    notion_client = AsyncClient(auth=notion_authentication_token)

    response_object = await notion_client.databases.query(
        notion_tasks_database_id,
        filter={
            "or": [
                {
                    "property": "Status",
                    "status": {
                        "equals": "In progress"
                    }
                },
                {
                    "property": "Status",
                    "status": {
                        "equals": "Not started"
                    }
                }
            ]
        })

    print("Task result:")
    for page in response_object["results"]:
        pprint.pprint(page)
        print("")

async def test_notion_query_people_parse():
    notion_client = AsyncClient(auth=notion_authentication_token)

    response_object = await notion_client.databases.query(
        notion_people_database_id)

    print("People database result:")
    for page in response_object["results"]:
        print("Person:")
        pprint.pprint(page["properties"]["Display Name"])
        pprint.pprint(page["properties"]["Notion Account"]["people"])
        pprint.pprint(page["properties"]["Discord"])
