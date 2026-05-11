import requests
import json
import time
from typing import Optional, Any


def fetch_text_with_retry(url: str, retries: int = 3, timeout: int = 10, headers: Optional[dict] = None) -> Optional[str]:
    """Fetch text content from a URL with exponential backoff / retry logic."""
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0'}
    
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                return None
            print(f"Fetch failed for {url} (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(1)
        except Exception as e:
            print(f"Fetch failed for {url} (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(1)
    return None


def fetch_json_with_retry(url: str, retries: int = 3, timeout: int = 10, headers: Optional[dict] = None) -> Optional[Any]:
    """Fetch and parse JSON from a URL with retry logic."""
    content = fetch_text_with_retry(url, retries, timeout, headers)
    if content is not None:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from {url}")
            return None
    return None
