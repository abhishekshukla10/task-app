import logging
import os
from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse

from ai_parser import parse_message
from sheets import add_task, list_tasks, complete_task

# -----------------------------
# LOGGING SETUP
# -----------------------------
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()          # Also prints to terminal
    ]
)

logger = logging.getLogger(__name__)

# -----------------------------
# FLASK APP
# -----------------------------
app = Flask(__name__)


# -----------------------------
# HEALTH CHECK (Required for Render)
# -----------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# -----------------------------
# WHATSAPP WEBHOOK
# -----------------------------
@app.route("/webhook", methods=["POST"])
def whatsapp_reply():
    resp = MessagingResponse()

    try:
        msg = request.form.get("Body", "").strip()
        sender = request.form.get("From", "unknown")

        logger.info(f"Message from {sender}: {msg}")

        # Guard: empty message
        if not msg:
            resp.message("Please send a message.")
            return str(resp)

        # Parse intent via Groq
        data = parse_message(msg)
        intent = data.get("intent", "unknown")

        logger.info(f"Parsed intent: {intent} | Data: {data}")

        # ---- ADD TASK ----
        if intent == "add":
            task = data.get("task", "").strip()
            if not task:
                resp.message(
                    "⚠️ Please specify a task. Example: Add task: Buy milk")
            elif add_task(task):
                resp.message(f"✅ Task added: *{task}*")
            else:
                resp.message("❌ Failed to save task. Please try again.")

        # ---- LIST TASKS ----
        elif intent == "list":
            tasks = list_tasks()
            if not tasks:
                resp.message("📭 No tasks found.")
            else:
                lines = [f"{i+1}. {row[0]} [{row[1]}]" for i,
                         row in enumerate(tasks)]
                resp.message("📋 *Your Tasks:*\n" + "\n".join(lines))

        # ---- COMPLETE TASK ----
        elif intent == "complete":
            try:
                task_num = int(data.get("task_number", 0))
                if complete_task(task_num):
                    resp.message(f"✅ Task {task_num} marked as *Done*")
                else:
                    resp.message(
                        "⚠️ Invalid task number. Send 'Show my tasks' to see the list.")
            except (ValueError, TypeError):
                resp.message("⚠️ Please say: *Complete task 2* (use a number)")

        # ---- UNKNOWN ----
        else:
            resp.message(
                "🤖 I can help you manage tasks.\n\n"
                "Try:\n"
                "➕ Add task: Buy milk\n"
                "📋 Show my tasks\n"
                "✅ Complete task 1"
            )

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        resp.message("❌ Something went wrong. Please try again.")

    return str(resp)


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
