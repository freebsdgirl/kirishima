import app.config

import requests


def _get_mal_synopsis(anime_id):
    """
    Retrieve the synopsis for an anime from MyAnimeList (MAL) using its ID.
    
    Args:
        anime_id (int): The unique identifier of the anime on MyAnimeList.
    
    Returns:
        str: The synopsis of the anime.
    """
    endpoint = f'{app.config.MAL_BASE_URL}/{anime_id}?fields=synopsis'
    response = requests.get(endpoint, headers={'X-MAL-CLIENT-ID': app.config.MAL_CLIENT_ID})
    data = response.json()
    return data['synopsis']


def _search_mal_for_id(query):
    """
    Search MyAnimeList (MAL) for an anime's ID and title based on a query.
    
    Args:
        query (str): The search term for the anime.
    
    Returns:
        tuple: A tuple containing the anime's ID and title, using the first result.
    """
    endpoint = f'{app.config.MAL_BASE_URL}?limit=1&fields=id&q={query}'
    response = requests.get(endpoint, headers={'X-MAL-CLIENT-ID': app.config.MAL_CLIENT_ID})
    data = response.json()
    return data['data'][0]['node']['id'],data['data'][0]['node']['title']


def search_mal_by_show(name):
    """
    Search MyAnimeList (MAL) for an anime's details by its name.
    
    Retrieves the anime's ID and title through a search query, then fetches its synopsis.
    
    Args:
        name (str): The name of the anime to search for.
    
    Returns:
        str: A formatted string containing the anime's name and synopsis.
    """
    show_id,show_title  = _search_mal_for_id(name)
    show_synopsis       = _get_mal_synopsis(show_id)

    return_value        = f"""Name: {show_title}

Synopsis: {show_synopsis}"""

    return return_value

