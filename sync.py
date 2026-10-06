import os
import sys
import requests
import json

"""
Originally taken from https://www.mediawiki.org/wiki/API%253AEdit/Sample_code_1
Modified for this purpose of syncing JSON data from an API to a wiki page.
"""

def get_or_error(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Couldn't fetch environment value for {name}!", file = sys.stderr)
        sys.exit(1)

    return value

USER_AGENT = get_or_error("USER_AGENT")

WIKI_URL = get_or_error("WIKI_URL")
API_URL = get_or_error("API_URL")

WIKI_USERNAME = get_or_error("WIKI_USERNAME")
WIKI_BOT_PASSWORD = get_or_error("WIKI_BOT_PASSWORD")

WIKI_PAGE = "Template:RailInfo/data"

def fetch_json(session: requests.Session) -> str:
    result = session.get(API_URL)
    result.raise_for_status()

    if not result.content:
        raise RuntimeError("Unable to fetch RailInfo JSON!")
    
    print(f"Received HTTP Status: {result.status_code}")
    print(f"Received Content-Type: {result.headers.get("Content-Type", "")}")

    try:
        # Validate that we got valid JSON
        result.json()
    except ValueError as err:
        raise RuntimeError(f"Received Non-JSON value! Received content Type: {result.headers.get("Content-Type", "")}") from err

    return result.text

def fetch_page_content(session: requests.Session) -> str:
    result = session.get(
        WIKI_URL,
        params = {
            "action": "query",
            "prop": "revisions",
            "titles": WIKI_PAGE,
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2"
        }
    )
    result.raise_for_status()

    try:
        data = result.json()

        print("Parsed Wiki Page JSON")

        pages = data["query"]["pages"]
        page = next(iter(pages.values()))

        if "missing" in page:
            return ""

        return page["revisions"][0]["slots"]["main"]["content"]
    except (ValueError, KeyError, IndexError, StopIteration) as err:
        raise RuntimeError(f"Unable to fetch current content of {WIKI_PAGE}. HTTP {result.status_code}: {result.text[:500]!r}") from err

def json_equal(first: str, second: str) -> bool:
    try:
        return json.loads(first) == json.loads(second)
    except ValueError as err:
        raise RuntimeError("Unable to compare Wiki and API JSON") from err

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
        login_token = result.json()["query"]["tokens"]["logintoken"]
    except (ValueError, KeyError) as err:
        raise RuntimeError(f"Unable to fetch Login Token. HTTP {result.status_code}: {result.text[:500]!r}") from err
    
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

    try:
        login_result = result.json()
    except ValueError as err:
        raise RuntimeError(f"Received Non-JSON Response from MediaWiki: {result.text[:500]!r}") from err
    
    if login_result.get("login", {}).get("result") != "Success":
        raise RuntimeError(f"Login failed: {login_result}")
    
    print("Logged into Wiki! Obtaining CSRF Token...")

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
    except (ValueError, KeyError) as err:
        raise RuntimeError(f"Couldn't fetch CSRF Token. HTTP {result.status_code}: {result.text[:500]!r}") from err
    
    return csrf_token

def update_page(session: requests.Session, csrf_token: str, content: str) -> None:
    result = session.post(
        WIKI_URL,
        data = {
            "action": "edit",
            "title": WIKI_PAGE,
            "format": "json",
            "text": content,
            "contentformat": "application/json",
            "contentmodel": "json",
            "bot": True,
            "token": csrf_token
        }
    )
    result.raise_for_status()

    try:
        edit = result.json()
    except ValueError as err:
        raise RuntimeError(f"Received non-JSON response from page edit: {result.text[:500]!r}") from err

    if "error" in edit:
        raise RuntimeError(f"Encountered Error while updating Wikipage {WIKI_PAGE}: {edit}")
    
    if edit.get("edit", {}).get("result") != "Success":
        raise RuntimeError(f"Received non-successful Wiki Edit: {edit}")
    
    new_revision = edit["edit"].get("newrevid")

    print(f"Updated {WIKI_PAGE} ({new_revision})")
    
def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    content = fetch_json(session)

    old_content = fetch_page_content(session)

    if json_equal(content, old_content):
        print(f"{WIKI_PAGE} is up-to-date. Skipping page edit.")
        return
    
    csrf_token = fetch_csrf_token(session)

    update_page(session, csrf_token, content)

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"ERROR: {err}", file = sys.stderr)
        sys.exit(1)
