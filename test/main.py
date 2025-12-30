# Run selected tests

from test.test import *
import asyncio

if __name__ == "__main__":
    asyncio.run(test_notion_query_people_parse())
