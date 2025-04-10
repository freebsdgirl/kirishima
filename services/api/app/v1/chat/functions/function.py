import api.config

from api.v1.chat.functions.rag.mal_show_synopsis import search_mal_by_show
from api.v1.chat.functions.memories import create_memory, delete_memory
from api.v1.chat.functions.mode import change_mode
from api.v1.chat.functions.scheduler import add_job, delete_job, list_jobs

from log_config import get_logger

logger = get_logger(__name__)


import re


def get_create_memory_matches(input):
    create_memory_pattern = re.compile(
        r'create_memory\(\s*[\'"]?(.+?)[\'"]?\s*,\s*([0-9]*\.?[0-9]+)\s*\)',
        re.IGNORECASE
    )

    return [(text, float(priority)) for text, priority in create_memory_pattern.findall(input)]


def get_delete_memory_matches(input):
    delete_memory_pattern = re.compile(
        r'delete_memory\(\s*[\'"]?(.+?)[\'"]?\s*\)',
        re.IGNORECASE
    )

    return delete_memory_pattern.findall(input)


def get_mode_matches(input):
    mode_pattern = re.compile(
        r'mode\(\s*[\'"]?(.+?)[\'"]?\s*\)',
        re.IGNORECASE
    )

    return mode_pattern.findall(input)


def get_search_mal_by_show_matches(input):
    search_mal_by_show_pattern = re.compile(
        r'search_mal_by_show\(\s*[\'"]?(.+?)[\'"]?\s*\)',
        re.IGNORECASE
    )

    return search_mal_by_show_pattern.findall(input)


def get_add_job_matches(input):
    add_job_pattern = re.compile(
        r'add_job\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*(\d{2}:\d{2}:\d{2})\s*\)',
        re.IGNORECASE
    )

    return add_job_pattern.findall(input)


def get_list_job_matches(input):
    list_job_pattern = re.compile(
        r'list_jobs\(\s*\)',
        re.IGNORECASE
    )

    return bool(list_job_pattern.search(input))


def get_delete_job_matches(input):
    delete_job_pattern = re.compile(
        r'delete_job\(\s*[\'"]?(.+?)[\'"]?\s*\)',
        re.IGNORECASE
    )

    return delete_job_pattern.findall(input)


def is_this_a_user_function(input):
    """
    Processes and executes user-specific function calls from input text.
    
    Parses the input for create_memory, delete_memory, mode, and search_mal_by_show function calls using regex,
    logs the detected function calls, and executes the corresponding functions.
    
    Args:
        input (str): The input text to search for user function calls.
    
    Returns:
        Optional[Any]: Returns results from search_mal_by_show if called, otherwise None.
    """
    logger.debug(f"📋 Checking for functions on user input: {input}")

    for memory, priority in get_create_memory_matches(input):
        logger.info(f"📜 function create_memory called with args: {memory} ({priority}).")
        create_memory(memory, priority)

    for match in get_delete_memory_matches(input):
        logger.info(f"📜 function delete_memory called with args: {match}.")
        delete_memory(match)

    for match in get_mode_matches(input):
        logger.info(f"🗃️ function mode called with args: {match}.")
        change_mode(match)

    for match in get_search_mal_by_show_matches(input):
        logger.info(f"📜 function search_mal_by_show called with args: {match}.")
        results = search_mal_by_show(match)
        return results

    for (function_name, interval_time) in get_add_job_matches(input):
        logger.info(f"🗃️ function add_job called with args: {function_name}, {interval_time}.")
        add_job(function_name, interval_time)

    for match in get_delete_job_matches(input):
        logger.info(f"🗃️ function delete_job called with args: {match}.")
        delete_job(match)

    if get_list_job_matches(input):
        logger.info(f"🗃️ function list_jobs called.")
        results = list_jobs()
        
        return results


async def is_this_a_llm_function(input):
    """
    Checks and processes LLM-specific function calls from input text.
    
    Parses the input for create_memory, delete_memory, and mode function calls using regex,
    logs the detected function calls, and executes the corresponding functions.
    
    Args:
        input (str): The input text to search for LLM function calls.
    
    Returns:
        None: Processes detected functions without returning a value.
    """
    logger.debug(f"📜 Checking for functions on nemo input: {input}")

    for match, priority in get_create_memory_matches(input):
        logger.info(f"📜 function create_memory called with args: {match}, {priority}.")
        create_memory(match, priority)

    for match in get_delete_memory_matches(input):
        logger.info(f"📜 function delete_memory called with args: {match}.")
        delete_memory(match)

    for match in get_mode_matches(input):
        logger.info(f"🗃️ function mode called with args: {match}.")
        change_mode(match)
    
