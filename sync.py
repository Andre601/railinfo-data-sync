import os
import sys
import requests

"""
Originally taken from https://www.mediawiki.org/wiki/API%253AEdit/Sample_code_1
"""

def get_or_error(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Couldn't fetch environment value for {name}!", file = sys.stderr)
        sys.exit(1)

    return value

WIKI_URL = get_or_error("WIKI_URL")
API_URL = get_or_error("API_URL")

WIKI_USERNAME = get_or_error("WIKI_USERNAME")
WIKI_BOT_PASSWORD = get_or_error("WIKI_BOT_PASSWORD")

WIKI_PAGE = "Module:RailInfo/data"

def fetch_json(session: requests.Session) -> str:
    result = session.get(API_URL)
    result.raise_for_status()

    if not result:
        raise RuntimeError("Unable to fetch RailInfo JSON!")

    return result.json()

def fetch_csrf_token(session: requests.Session) -> str:
    result = session.get(
        WIKI_URL,
        params = {
            "action": "query",
            "meta": "tokens",
            "type": "login",
            "format": "json"
        }
    )
    result.raise_for_status()

    try:
        login_token = result["query"]["tokens"]["logintoken"]
    except KeyError as err:
        raise RuntimeError(f"Unable to fetch Login Token: {result}") from err
    
    result = session.post(
        WIKI_URL,
        data = {
            "action": "login",
            "lgname": WIKI_USERNAME,
            "lgpassword": WIKI_BOT_PASSWORD,
            "lgtoken": login_token,
            "format": "json"
        }
    )
    result.raise_for_status()

    result = session.get(
        WIKI_URL,
        params = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }
    )
    result.raise_for_status()

    try:
        csrf_token = result.json()["query"]["tokens"]["csrftoken"]
    except KeyError as err:
        raise RuntimeError(f"Couldn't fetch CSRF Token: {result}") from err
    
    return csrf_token

def update_page(session: requests.Session, csrf_token: str, content: str) -> None:
    result = session.post(
        WIKI_URL,
        data = {
            "action": "edit",
            "title": WIKI_PAGE,
            "token": csrf_token,
            "format": "json",
            "text": content,
            "contentmodel": "json"
        }
    )
    result.raise_for_status()

    if "error" in result:
        raise RuntimeError(f"Encountered Error while updating Wikipage {WIKI_PAGE}: {result}")
    
    edit = result.get("edit", {})

    if edit.get("result") != "Success":
        raise RuntimeError(f"Edit of Wiki page {WIKI_PAGE} non-successful! {result}")
    
    print(f"Updated {WIKI_PAGE} ({edit.get("newrevid")})")
    
def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "RailInfo-Wikisync/1.0"})

    content = fetch_json(session)
    csrf_token = fetch_csrf_token(session)

    update_page(session, csrf_token, content)

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"ERROR: {err}", file = sys.stderr)
        sys.exit(1)