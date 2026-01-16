# Test module, defines tests

from bot.config import notion_authentication_token, notion_events_database_id, \
    notion_tasks_database_id, notion_people_database_id
from bot.utils.notion import NotionConnection
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
    notion = NotionConnection(
            notion_auth_token=notion_authentication_token,
            events_db_id=notion_events_database_id,
            tasks_db_id=notion_tasks_database_id,
            people_db_id=notion_people_database_id)

    response_object = notion.get_tasks_from_notion()

    print("Task result:")
    for page in response_object["results"]:
        pprint.pprint(page)
        print("")

async def test_notion_query_event_parse():
    notion = NotionConnection(
            notion_auth_token=notion_authentication_token,
            events_db_id=notion_events_database_id,
            tasks_db_id=notion_tasks_database_id,
            people_db_id=notion_people_database_id)

    response_object = notion.get_events_from_notion()

    print("Event database result:")
    for page in response_object["results"]:
        pprint.pprint(page)
        print("")
