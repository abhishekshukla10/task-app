import logging
import json
import os
import datetime
import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_SHEET_NAME

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_sheet():
    """
    Reads credentials from ENV variable (works on Render)
    Falls back to credentials.json (works locally)
    """
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

        if creds_json:
            # Running on Render — read from env variable
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )
        else:
            # Running locally — read from file
            creds = Credentials.from_service_account_file(
                'credentials.json', scopes=SCOPES
            )

        client = gspread.authorize(creds)
        return client.open(GOOGLE_SHEET_NAME).sheet1

    except FileNotFoundError:
        logger.error("credentials.json not found")
        raise
    except Exception as e:
        logger.error(f"Google Sheets connection error: {e}")
        raise


def add_task(task: str) -> bool:
    """Appends a new task row. Returns True on success."""
    try:
        sheet = get_sheet()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet.append_row([task, "Pending", now])
        logger.info(f"Task added: {task}")
        return True
    except Exception as e:
        logger.error(f"add_task failed: {e}")
        return False


def list_tasks() -> list:
    """Returns all task rows (excluding header). Empty list on failure."""
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        # Skip header row if present
        return rows[1:] if len(rows) > 1 else []
    except Exception as e:
        logger.error(f"list_tasks failed: {e}")
        return []


def complete_task(task_num: int) -> bool:
    """
    Marks task at task_num (1-indexed) as Done.
    Returns True on success, False on invalid number or error.
    """
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        total_tasks = len(rows) - 1  # Exclude header

        if task_num < 1 or task_num > total_tasks:
            logger.warning(
                f"Invalid task number: {task_num}, total: {total_tasks}")
            return False

        sheet.update_cell(task_num + 1, 2, "Done")  # +1 to skip header
        logger.info(f"Task {task_num} marked Done")
        return True

    except Exception as e:
        logger.error(f"complete_task failed: {e}")
        return False
