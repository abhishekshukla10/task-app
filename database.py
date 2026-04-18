import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Valid status values — single source of truth
VALID_STATUSES = ["Pending", "WIP", "Complete", "Dropped"]

# -----------------------------
# CONNECTION
# -----------------------------


def get_db():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise EnvironmentError("DATABASE_URL is missing from .env")
    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    return conn


# -----------------------------
# INIT TABLES
# -----------------------------
def init_db():
    """Creates tables on startup if they don't exist."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                phone_number  TEXT UNIQUE,          -- WhatsApp identity
                email         TEXT UNIQUE,          -- Browser login
                password_hash TEXT,                 -- Browser users only
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                task       TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'Pending'
                               CHECK (status IN ('Pending','WIP','Complete','Dropped')),
                remarks    TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        logger.info("Database initialized successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"init_db failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


# -----------------------------
# USER FUNCTIONS
# -----------------------------
def get_or_create_whatsapp_user(phone_number: str) -> int:
    """
    Finds WhatsApp user by phone number.
    Creates new user automatically if first time.
    Returns user_id.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM users WHERE phone_number = %s",
            (phone_number,)
        )
        user = cursor.fetchone()

        if user:
            return user["id"]

        # First time this phone number — auto register
        cursor.execute(
            "INSERT INTO users (phone_number) VALUES (%s) RETURNING id",
            (phone_number,)
        )
        new_user = cursor.fetchone()
        conn.commit()
        logger.info(f"New WhatsApp user registered: {phone_number}")
        return new_user["id"]

    except Exception as e:
        conn.rollback()
        logger.error(f"get_or_create_whatsapp_user failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


# -----------------------------
# TASK FUNCTIONS
# -----------------------------
def add_task(user_id: int, task: str) -> bool:
    """Adds a new Pending task for a user."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO tasks (user_id, task) VALUES (%s, %s)",
            (user_id, task)
        )
        conn.commit()
        logger.info(f"Task added for user {user_id}: {task}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"add_task failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def list_tasks(user_id: int) -> list:
    """Returns all tasks for a user, oldest first."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, task, status, remarks, created_at, updated_at
            FROM tasks
            WHERE user_id = %s
            ORDER BY created_at ASC
        """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"list_tasks failed: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def update_task_status(user_id: int, task_num: int, new_status: str) -> bool:
    """
    Updates status of Nth task for a user.
    task_num is 1-indexed (as shown to user).
    new_status must be one of: Pending, WIP, Complete, Dropped
    """
    if new_status not in VALID_STATUSES:
        logger.warning(f"Invalid status: {new_status}")
        return False

    conn = get_db()
    cursor = conn.cursor()
    try:
        # Get tasks in order to find the Nth one
        cursor.execute("""
            SELECT id FROM tasks
            WHERE user_id = %s
            ORDER BY created_at ASC
        """, (user_id,))
        tasks = cursor.fetchall()

        if task_num < 1 or task_num > len(tasks):
            logger.warning(f"Invalid task number: {task_num}")
            return False

        task_id = tasks[task_num - 1]["id"]

        cursor.execute("""
            UPDATE tasks
            SET status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """, (new_status, task_id, user_id))

        conn.commit()
        logger.info(
            f"Task {task_num} status → {new_status} for user {user_id}")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"update_task_status failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def edit_task_text(user_id: int, task_num: int, new_text: str) -> bool:
    """
    Edits the text of Nth task for a user.
    This is the 'edit task' provision you asked for.
    """
    if not new_text or not new_text.strip():
        return False

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM tasks
            WHERE user_id = %s
            ORDER BY created_at ASC
        """, (user_id,))
        tasks = cursor.fetchall()

        if task_num < 1 or task_num > len(tasks):
            return False

        task_id = tasks[task_num - 1]["id"]

        cursor.execute("""
            UPDATE tasks
            SET task = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """, (new_text.strip(), task_id, user_id))

        conn.commit()
        logger.info(f"Task {task_num} text edited for user {user_id}")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"edit_task_text failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def add_remark(user_id: int, task_num: int, remark: str) -> bool:
    """Adds or updates a remark on a task."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM tasks
            WHERE user_id = %s
            ORDER BY created_at ASC
        """, (user_id,))
        tasks = cursor.fetchall()

        if task_num < 1 or task_num > len(tasks):
            return False

        task_id = tasks[task_num - 1]["id"]

        cursor.execute("""
            UPDATE tasks
            SET remarks = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """, (remark.strip(), task_id, user_id))

        conn.commit()
        logger.info(f"Remark added to task {task_num} for user {user_id}")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"add_remark failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def delete_task(user_id: int, task_num: int) -> bool:
    """Deletes a task permanently."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM tasks
            WHERE user_id = %s
            ORDER BY created_at ASC
        """, (user_id,))
        tasks = cursor.fetchall()

        if task_num < 1 or task_num > len(tasks):
            return False

        task_id = tasks[task_num - 1]["id"]

        cursor.execute(
            "DELETE FROM tasks WHERE id = %s AND user_id = %s",
            (task_id, user_id)
        )
        conn.commit()
        logger.info(f"Task {task_num} deleted for user {user_id}")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"delete_task failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
