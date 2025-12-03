from notion_client import AsyncClient, Client
import os
import asyncio
from dotenv import load_dotenv

class NotionConnection:
    """
    NotionConnection class. Used to decouple the notion connection from other classes/cogs.
    """
    def __init__(self, notion_auth_token, events_db_id="", tasks_db_id="", people_db_id=""):
        self.notion_client = AsyncClient(auth=notion_auth_token)
        self.events_db_id = events_db_id
        self.tasks_db_id = tasks_db_id
        self.people_db_id= people_db_id

    def set_events_db_id(self, events_db_id):
        self.events_db_id = events_db_id

    def set_tasks_db_id(self, tasks_db_id):
        self.tasks_db_id = tasks_db_id

    def set_people_db_id(self, people_db_id):
        self.people_db_id = people_db_id

    async def get_events_from_notion(self):
        notion_events_public_filter = {
            "property": "Public Checkbox",
            "checkbox": {
                "equals": True
            }
        }

        response_object = await self.notion_client.data_sources.query(
            self.events_db_id,
            filter=notion_events_public_filter
        )

        return response_object
    
    async def get_tasks_from_notion(self):
        notion_tasks_completed_filter = {
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
        }

        response_object = await self.notion_client.data_sources.query(
                self.tasks_db_id,
                filter=notion_tasks_completed_filter)
        
        return response_object

    async def get_people_from_notion(self):
        response_object = await self.notion_client.data_sources.query(
                self.people_db_id)
        
        return response_object

if __name__ == "__main__":
    load_dotenv()
    notion_connection = NotionConnection(os.environ["NOTION_AUTHENTICATION_TOKEN"])
    notion_connection.set_events_db_id(os.environ["NOTION_EVENTS_DATABASE_ID"])
    notion_connection.set_tasks_db_id(os.environ["NOTION_TASKS_DATABASE_ID"])
    res = asyncio.run(notion_connection.get_tasks_from_notion())
