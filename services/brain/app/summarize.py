"""
this file is about to be obsolete.
"""

from datetime import datetime, timezone, timedelta
import sqlite3
import app.config
import requests
import os

from shared.log_config import get_logger

logger = get_logger(__name__)

def recently_summarized() -> bool:
    """
    Check if a summary has been generated recently based on the last recorded timestamp.
    
    Returns:
        bool: True if a summary was generated within the minimum interval, False otherwise.
        Returns False if the timestamp file does not exist or cannot be read.
    """
    if not os.path.exists(app.config.LAST_SUMMARY_TIMESTAMP_FILE):
        return False
    try:
        with open(app.config.LAST_SUMMARY_TIMESTAMP_FILE, "r") as f:
            last_run = float(f.read().strip())
        now = datetime.now(timezone.utc).timestamp()
        return (now - last_run) < app.config.MIN_SUMMARY_INTERVAL_SECONDS
    except:
        return False


def format_buffer_for_summary(buffer: list[dict]) -> str:
    """
    Convert a list of message dicts into a clean, human-readable string for summarization.

    Args:
        buffer (list[dict]): Each message should contain 'sender' and 'content'.

    Returns:
        str: A newline-separated string of formatted conversation lines.
    """
    return "\n".join(f"{msg['sender'].capitalize()}: {msg['content']}" for msg in buffer if msg.get("content"))


def summarize_text(text) -> str:
    """
    Generate a summary of a conversation using a local AI model.
    
    Args:
        text (list[dict]): A list of message dictionaries to be summarized.
    
    Returns:
        str: A concise single-paragraph summary of the conversation, or an empty string if summarization fails.
    
    Raises:
        Logs any errors encountered during the summarization process.
    """
    if isinstance(text, list):
        formatted_text = format_buffer_for_summary(text)
    else:
        formatted_text = text

    prompt = f"""Summarize the following conversation in a single paragraph:


[START CONVERSATION]

{formatted_text}

[END CONVERSATION]


Summarize the previous conversation in a single descriptive paragraph.
Do not include commentary, apologies, system messages, or statements about being an AI.
Only return the summary.
"""


    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "deepseek:latest",
                "prompt": prompt,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        import logging
        logging.error(f"Error during summarization: {e}")
        return ""


def parse_iso_timestamp(ts_str: str) -> datetime:
    """
    Parses an ISO 8601 timestamp string into a timezone-aware datetime object.
    
    Converts 'Z' timezone notation to '+00:00' and ensures the resulting datetime
    has UTC timezone information.
    
    Args:
        ts_str (str): An ISO 8601 formatted timestamp string.
    
    Returns:
        datetime: A timezone-aware datetime object in UTC.
    """
    if ts_str.endswith("Z"):
        ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_conversation_active(messages: list) -> bool:
    """
    Determines if the conversation is active based on message density and recency.
    
    Active if:
      - The last message was sent within IDLE_THRESHOLD_MINUTES, and
      - The conversation's timespan is within DENSITY_THRESHOLD_MINUTES with at least DENSITY_THRESHOLD_LINES messages.
    
    Returns:
        True if the conversation is considered active, otherwise False.
    """
    if not messages:
        return False

    first_ts = parse_iso_timestamp(messages[0]['timestamp'])
    last_ts = parse_iso_timestamp(messages[-1]['timestamp'])
    now = datetime.now(timezone.utc)

    # Check idle condition: inactive if more than IDLE_THRESHOLD_MINUTES have passed since the last message.
    if now - last_ts > timedelta(minutes=app.config.IDLE_THRESHOLD_MINUTES):
        return False

    # Check density: active if the conversation's time span is within the threshold and has enough messages.
    if (last_ts - first_ts <= timedelta(minutes=app.config.DENSITY_THRESHOLD_MINUTES)) and (len(messages) >= app.config.DENSITY_THRESHOLD_LINES):
        return True

    return False


def load_messages(conn: sqlite3.Connection) -> list:
    """
    Retrieves all messages from the rolling_buffer database table, sorted chronologically.
    
    Fetches messages with their sender, content, timestamp, platform, and mode,
    and returns them as a list of dictionaries ordered by timestamp.
    
    Args:
        conn (sqlite3.Connection): An active SQLite database connection.
    
    Returns:
        list: A list of message dictionaries, sorted chronologically.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, content, timestamp, platform, mode FROM rolling_buffer ORDER BY timestamp"
    )
    rows = cursor.fetchall()
    messages = [{
        "sender": row[0],
        "content": row[1],
        "timestamp": row[2],
        "platform": row[3],
        "mode": row[4]
    } for row in rows]
    return messages


def insert_summary(conn: sqlite3.Connection, summary: str, stage: int = 1, ts: str = None):
    """
    Inserts a summary into the summaries database table.
    
    Stores a conversation summary with a given timestamp and processing stage.
    If ts is not provided, the current timestamp is used.
    
    Args:
        conn (sqlite3.Connection): An active SQLite database connection.
        summary (str): The text summary to be stored.
        stage (int, optional): The processing stage of the summary. Defaults to 1.
        ts (str, optional): The timestamp to record for this summary. Defaults to None.
    """
    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO summaries (summary, timestamp, stage) VALUES (?, ?, ?)",
        (summary, ts, stage)
    )
    conn.commit()


def summarize_and_purge_messages(conn: sqlite3.Connection, messages: list, conversation_active: bool):
    """
    Summarizes and removes messages from the rolling buffer based on conversation activity.
    
    Handles message summarization for both active and inactive conversations, generating
    a summary using an LLM and removing processed messages from the database.
    
    Args:
        conn (sqlite3.Connection): Active database connection.
        messages (list): List of messages to potentially summarize.
        conversation_active (bool): Flag indicating current conversation activity status.
    """
    cursor = conn.cursor()

    if conversation_active:
        if len(messages) >= app.config.SUMMARIZE_THRESHOLD_ACTIVE:
            to_summarize = messages[:app.config.SUMMARIZE_CHUNK_SIZE]
        else:
            logger.info("Active conversation detected but not enough messages to summarize.")
            return
    else:
        to_summarize = messages

    # Generate summary using your LLM-based summarization function.
    summary = summarize_text(to_summarize)

    # Use the oldest message's timestamp from the batch
    oldest_ts = to_summarize[0]['timestamp'] if to_summarize else datetime.now(timezone.utc).isoformat()

    # Insert the summary with the oldest timestamp
    insert_summary(conn, summary, stage=1, ts=oldest_ts)

    # Purge the summarized messages from the rolling_buffer.
    if conversation_active:
        for msg in to_summarize:
            cursor.execute(
                "DELETE FROM rolling_buffer WHERE sender = ? AND content = ? AND timestamp = ? AND platform = ? AND mode = ?",
                (msg['sender'], msg['content'], msg['timestamp'], msg['platform'], msg['mode'])
            )
    else:
        cursor.execute("DELETE FROM rolling_buffer")

    conn.commit()

    with open(app.config.LAST_SUMMARY_TIMESTAMP_FILE, "w") as f:
        f.write(str(datetime.now(timezone.utc).timestamp()))

    logger.info(f"Summarized and purged {len(to_summarize)} messages.")


def check_and_summarize():
    """
    Manages the summarization process for conversation messages in the rolling buffer.
    
    Checks if summarization is needed, loads messages, determines conversation activity,
    and triggers message summarization. Handles database connection and error management
    for the summarization workflow.
    
    Performs the following key steps:
    - Checks if recent summarization has occurred
    - Loads messages from the rolling buffer
    - Determines conversation activity status
    - Summarizes and purges messages
    - Triggers meta-summary generation
    - Handles potential exceptions during the process
    """
    logger.info("Checking conversation buffer for summarization conditions...")

    if recently_summarized():
        logger.info("Skipping summarization: recently summarized.")
        return

    try:
        conn = sqlite3.connect(app.config.ROLLING_BUFFER_DB)
        messages = load_messages(conn)
        
        if not messages:
            logger.info("Buffer is empty; nothing to summarize.")
            return

        conversation_active = is_conversation_active(messages)
        summarize_and_purge_messages(conn, messages, conversation_active)
        check_meta_summaries()
    except Exception as e:
        logger.error(f"Error during summarization: {e}")
    finally:
        conn.close()


def meta_summarize(conn: sqlite3.Connection, source_stage: int, target_stage: int, trigger_count: int, chunk_size: int):
    """
    Performs meta-summarization by merging a chunk of summaries from one stage into a new summary in the target stage.
    
    Args:
        conn: Active SQLite database connection.
        source_stage: The source stage of summaries to be merged.
        target_stage: The target stage where the new meta-summary will be created.
        trigger_count: Minimum number of summaries required to initiate meta-summarization.
        chunk_size: Number of summaries to merge in a single meta-summarization operation.
    
    Merges the oldest summaries from the source stage, creates a new summary, and removes the original summaries.
    Logs the meta-summarization process and skips if insufficient summaries are available.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, summary, timestamp FROM summaries WHERE stage = ? ORDER BY timestamp",
        (source_stage,)
    )
    summaries = cursor.fetchall()
    
    if len(summaries) < trigger_count:
        logger.info(f"Not enough summaries in Stage {source_stage} to trigger meta-summarization. Found {len(summaries)}.")
        return

    # Merge the oldest `chunk_size` summaries.
    to_merge = summaries[:chunk_size]
    merged_text = "\n".join([row[1] for row in to_merge])
    new_summary = summarize_text(merged_text)
    
    # Use the oldest timestamp from the merged summaries
    oldest_meta_ts = to_merge[0][2] if to_merge else datetime.now(timezone.utc).isoformat()
    
    cursor.execute(
        "INSERT INTO summaries (summary, timestamp, stage) VALUES (?, ?, ?)",
        (new_summary, oldest_meta_ts, target_stage)
    )
    
    ids_to_delete = [row[0] for row in to_merge]
    delete_query = "DELETE FROM summaries WHERE id IN ({seq})".format(seq=','.join(['?'] * len(ids_to_delete)))
    cursor.execute(delete_query, ids_to_delete)
    conn.commit()
    logger.info(f"Merged {len(to_merge)} Stage {source_stage} summaries into a Stage {target_stage} summary.")


def enforce_stage3_limit(conn: sqlite3.Connection, max_stage3: int):
    """
    Ensures that no more than `max_stage3` Stage 3 summaries exist.
    If the limit is exceeded, delete the oldest summaries to maintain the cap.
    
    Args:
        conn: Active SQLite connection.
        max_stage3: Maximum allowed number of Stage 3 summaries.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM summaries WHERE stage = 3 ORDER BY timestamp"
    )
    stage3_summaries = cursor.fetchall()
    if len(stage3_summaries) > max_stage3:
        delete_count = len(stage3_summaries) - max_stage3
        ids_to_delete = [row[0] for row in stage3_summaries[:delete_count]]
        delete_query = "DELETE FROM summaries WHERE id IN ({seq})".format(seq=','.join(['?'] * len(ids_to_delete)))
        cursor.execute(delete_query, ids_to_delete)
        conn.commit()
        logger.info(f"Stage 3 limit enforced. Deleted {delete_count} oldest Stage 3 summaries.")


def check_meta_summaries():
    """
    Checks for and triggers meta-summarization for Stage 2 and Stage 3.
    
    - Stage 2: If at least 10 Stage 1 summaries exist, merge the oldest 5 into one Stage 2 summary.
    - Stage 3: If at least 10 Stage 2 summaries exist, merge the oldest 5 into one Stage 3 summary,
      then enforce that only 10 Stage 3 summaries are retained.
    """
    try:
        conn = sqlite3.connect(app.config.ROLLING_BUFFER_DB)
        # Stage 2 meta-summarization
        meta_summarize(conn, source_stage=1, target_stage=2, trigger_count=10, chunk_size=5)
        # Stage 3 meta-summarization
        meta_summarize(conn, source_stage=2, target_stage=3, trigger_count=10, chunk_size=5)
        # Enforce retention limit on Stage 3 summaries
        enforce_stage3_limit(conn, max_stage3=10)
    except Exception as e:
        logger.error(f"Error during meta-summarization: {e}")
    finally:
        conn.close()
