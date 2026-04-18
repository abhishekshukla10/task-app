import re
import json
import logging
from groq import Groq
from config import GROQ_API_KEY

logger = logging.getLogger(__name__)
client_ai = Groq(api_key=GROQ_API_KEY)


def parse_message(user_input: str) -> dict:
    """
    Sends user message to Groq and returns parsed intent as dict.
    Always returns a dict — never raises.
    """
    if not user_input or not user_input.strip():
        logger.warning("parse_message called with empty input")
        return {"intent": "unknown"}

    prompt = f"""
        
    You are a task assistant. Extract intent from message.

    Return ONLY JSON:
    {{
    "intent": "add/list/complete/wip/drop/edit/remark/delete/unknown",
    "task": "",
    "task_number": "",
    "new_text": "",
    "remark": ""
    }}

    Examples:
    "Add task: Buy milk"         → {{"intent":"add","task":"buy milk"}}
    "Show my tasks"              → {{"intent":"list"}}
    "Complete task 2"            → {{"intent":"complete","task_number":"2"}}
    "Mark task 3 as WIP"         → {{"intent":"wip","task_number":"3"}}
    "Drop task 1"                → {{"intent":"drop","task_number":"1"}}
    "Edit task 2: Call client"   → {{"intent":"edit","task_number":"2","new_text":"Call client"}}
    "Add remark to task 1: urgent" → {{"intent":"remark","task_number":"1","remark":"urgent"}}
    "Delete task 3"              → {{"intent":"delete","task_number":"3"}}

    Message: {user_input}
    """

    try:
        response = client_ai.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system",
                    "content": "You are a strict JSON generator. Return only JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        text = response.choices[0].message.content
        logger.debug(f"Groq raw response: {text}")

        # Extract JSON safely
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())

        logger.warning(f"No JSON found in Groq response: {text}")
        return {"intent": "unknown"}

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {"intent": "unknown"}

    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return {"intent": "unknown"}
