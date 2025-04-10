def get_current_time():
    """
    Get the current timestamp as a formatted prompt string.
    
    Returns:
        str: A prompt string containing the current local timestamp.
    """
    from datetime import datetime
    timestamp = datetime.now().astimezone()
    
    prompt = f"""The current time is {timestamp}."""

    return prompt