import requests
import config

api_key = config.get_credentials()["notion"]["api_key"]

res = requests.post(
    "https://api.notion.com/v1/search",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    },
    json={"filter": {"value": "database", "property": "object"}}
)

data = res.json()

if "results" not in data:
    print("Error:", data)
else:
    print(f"Found {len(data['results'])} databases:\n")
    for result in data["results"]:
        title_list = result.get("title", [])
        title_text = title_list[0]["plain_text"] if title_list else "Untitled"
        print(f"Title: {title_text}")
        print(f"ID: {result['id']}")
        print("---")