import logging
import os
from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse

from ai_parser import parse_message
from database import (
    init_db, get_or_create_whatsapp_user,
    add_task, list_tasks, update_task_status,
    edit_task_text, add_remark, delete_task
)

# -----------------------------
# LOGGING SETUP
# -----------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -----------------------------
# FLASK APP
# -----------------------------
app = Flask(__name__)
init_db()  # Creates tables on startup if not exist


# -----------------------------
# HEALTH CHECK
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

        # Identify user automatically by phone number
        user_id = get_or_create_whatsapp_user(sender)

        # Parse intent via Groq
        data = parse_message(msg)
        intent = data.get("intent", "unknown")
        logger.info(f"Intent: {intent} | Data: {data}")

        # ---- ADD TASK ----
        if intent == "add":
            task = data.get("task", "").strip()
            if not task:
                resp.message(
                    "⚠️ Please specify a task.\nExample: Add task: Buy milk")
            elif add_task(user_id, task):
                resp.message(f"✅ Task added: *{task}*")
            else:
                resp.message("❌ Failed to save task. Try again.")

        # ---- LIST TASKS ----
        elif intent == "list":
            tasks = list_tasks(user_id)
            if not tasks:
                resp.message("📭 No tasks found.")
            else:
                lines = []
                for i, row in enumerate(tasks, 1):
                    lines.append(f"{i}. {row['task']} [{row['status']}]")
                resp.message("📋 *Your Tasks:*\n" + "\n".join(lines))

        # ---- COMPLETE TASK ----
        elif intent == "complete":
            try:
                task_num = int(data.get("task_number", 0))
                if update_task_status(user_id, task_num, "Complete"):
                    resp.message(f"✅ Task {task_num} marked as *Complete*")
                else:
                    resp.message("⚠️ Invalid task number.")
            except (ValueError, TypeError):
                resp.message("⚠️ Say: *Complete task 2*")

        # ---- MARK WIP ----
        elif intent == "wip":
            try:
                task_num = int(data.get("task_number", 0))
                if update_task_status(user_id, task_num, "WIP"):
                    resp.message(f"🔄 Task {task_num} marked as *WIP*")
                else:
                    resp.message("⚠️ Invalid task number.")
            except (ValueError, TypeError):
                resp.message("⚠️ Say: *Mark task 2 as WIP*")

        # ---- DROP TASK ----
        elif intent == "drop":
            try:
                task_num = int(data.get("task_number", 0))
                if update_task_status(user_id, task_num, "Dropped"):
                    resp.message(f"🗑️ Task {task_num} marked as *Dropped*")
                else:
                    resp.message("⚠️ Invalid task number.")
            except (ValueError, TypeError):
                resp.message("⚠️ Say: *Drop task 2*")

        # ---- EDIT TASK TEXT ----
        elif intent == "edit":
            try:
                task_num = int(data.get("task_number", 0))
                new_text = data.get("new_text", "").strip()
                if not new_text:
                    resp.message(
                        "⚠️ Please provide new task text.\nExample: Edit task 2: Call client")
                elif edit_task_text(user_id, task_num, new_text):
                    resp.message(
                        f"✏️ Task {task_num} updated to: *{new_text}*")
                else:
                    resp.message("⚠️ Invalid task number.")
            except (ValueError, TypeError):
                resp.message("⚠️ Say: *Edit task 2: New task text*")

        # ---- ADD REMARK ----
        elif intent == "remark":
            try:
                task_num = int(data.get("task_number", 0))
                remark = data.get("remark", "").strip()
                if not remark:
                    resp.message(
                        "⚠️ Please provide a remark.\nExample: Remark task 1: urgent")
                elif add_remark(user_id, task_num, remark):
                    resp.message(f"📝 Remark added to task {task_num}")
                else:
                    resp.message("⚠️ Invalid task number.")
            except (ValueError, TypeError):
                resp.message("⚠️ Say: *Add remark to task 1: urgent*")

        # ---- DELETE TASK ----
        elif intent == "delete":
            try:
                task_num = int(data.get("task_number", 0))
                if delete_task(user_id, task_num):
                    resp.message(f"🗑️ Task {task_num} deleted permanently")
                else:
                    resp.message("⚠️ Invalid task number.")
            except (ValueError, TypeError):
                resp.message("⚠️ Say: *Delete task 2*")

        # ---- UNKNOWN ----
        else:
            resp.message(
                "🤖 *Task Manager Commands:*\n\n"
                "➕ Add task: Buy milk\n"
                "📋 Show my tasks\n"
                "✅ Complete task 1\n"
                "🔄 Mark task 2 as WIP\n"
                "🗑️ Drop task 3\n"
                "✏️ Edit task 2: New text\n"
                "📝 Remark task 1: urgent\n"
                "❌ Delete task 2"
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
    app.run(host="0.0.0.0", port=port, debug=True)
