from shared.models.smarthome import MediaEvent

from fastapi import HTTPException
from typing import Dict, Any, List
import sqlite3
import json
from datetime import datetime

from app.setup import get_db_path
from shared.log_config import get_logger

logger = get_logger(f"smarthome.{__name__}")


def _determine_time_of_day() -> str:
    """Determine current time of day category."""
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 22:
        return "evening"
    else:
        return "night"


def _categorize_media_content(event: MediaEvent) -> str:
    """Determine media content type from app name and available metadata."""
    # Explicit content type if provided
    if event.media_content_type:
        return event.media_content_type.lower()
    
    # App-based detection
    if event.app_name:
        app_lower = event.app_name.lower()
        
        # Music apps
        if any(music_app in app_lower for music_app in ['music', 'spotify', 'apple music', 'music assistant']):
            return 'music'
            
        # Video streaming apps
        if any(video_app in app_lower for video_app in ['crunchyroll', 'netflix', 'hulu', 'disney', 'amazon']):
            return 'tvshow'  # Could be refined later based on metadata
            
        # Movie apps
        if any(movie_app in app_lower for movie_app in ['apple tv', 'movies', 'vudu']):
            return 'movie'
    
    # Metadata-based detection
    if event.media_artist and event.media_album:
        return 'music'
    elif event.media_series_title or event.media_season:
        return 'tvshow'  
    elif event.media_year and not event.media_series_title:
        return 'movie'
    
    # Default fallback
    return 'unknown'


async def _track_media_event(event: MediaEvent) -> Dict[str, Any]:
    """
    Track a media event from Home Assistant or Music Assistant.
    
    This endpoint is designed to be called by Home Assistant automations
    whenever media state changes on any device.
    """
    try:
        # Use provided timestamp or current time
        event_time = event.timestamp or datetime.now()
        
        # Categorize the media content
        content_type = _categorize_media_content(event)

        # Get current context
        time_of_day = _determine_time_of_day()
        
        # Store the raw event
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO media_events (
                    timestamp, device_id, device_name, app_name, media_content_type,
                    media_title, media_duration, media_position,
                    media_artist, media_album, media_album_artist, media_track,
                    media_series_title, media_season, media_episode, media_year,
                    event_type, raw_attributes, time_of_day
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_time, event.device_id, event.device_name, event.app_name, content_type,
                event.media_title, event.media_duration, event.media_position,
                event.media_artist, event.media_album, event.media_album_artist, event.media_track,
                event.media_series_title, event.media_season, event.media_episode, event.media_year,
                event.event_type, json.dumps(event.raw_attributes) if event.raw_attributes else None,
                time_of_day
            ))
            
            # Update preference tables based on content type
            if content_type == 'music' and event.media_artist and event.media_title:
                await _update_music_preferences(conn, event, event_time, time_of_day)
            elif content_type == 'tvshow' and (event.media_series_title or event.media_title):
                await _update_tv_preferences(conn, event, event_time, time_of_day)
            elif content_type == 'movie' and event.media_title:
                await _update_movie_preferences(conn, event, event_time, time_of_day)
            
            conn.commit()
        
        logger.info(f"Tracked {content_type} event: {event.event_type} - {event.media_title}")
        
        return {
            "status": "success",
            "message": f"Media event tracked successfully",
            "content_type": content_type,
            "time_of_day": time_of_day
        }
        
    except Exception as e:
        logger.exception(f"Error tracking media event: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to track media event: {str(e)}"
        )


async def _update_music_preferences(conn: sqlite3.Connection, event: MediaEvent, event_time: datetime, time_of_day: str):
    """Update music preferences based on the event."""
    # Calculate play time (if this is a meaningful play event)
    play_time = 0
    if event.event_type == 'play' and event.media_duration and event.media_position:
        play_time = min(event.media_duration - event.media_position, event.media_duration)
    
    # Skip tracking if this is a skip event
    skip_increment = 1 if event.event_type == 'skip' else 0
    play_increment = 1 if event.event_type == 'play' else 0
    
    conn.execute("""
        INSERT INTO music_preferences (
            artist, album, track_title, play_count, total_play_time, 
            last_played, first_played, skip_count, preferred_time_of_day
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(artist, album, track_title) DO UPDATE SET
            play_count = play_count + ?,
            total_play_time = total_play_time + ?,
            last_played = ?,
            skip_count = skip_count + ?,
            preferred_time_of_day = CASE 
                WHEN play_count < 5 THEN ?
                ELSE preferred_time_of_day 
            END
    """, (
        event.media_artist, event.media_album, event.media_title,
        play_increment, play_time, event_time, event_time, skip_increment, time_of_day,
        # ON CONFLICT updates
        play_increment, play_time, event_time, skip_increment, time_of_day
    ))


async def _update_tv_preferences(conn: sqlite3.Connection, event: MediaEvent, event_time: datetime, time_of_day: str):
    """Update TV show preferences based on the event."""
    series_title = event.media_series_title or event.media_title
    
    # Calculate completion percentage if we have duration and position
    completion = 0.0
    if event.media_duration and event.media_position:
        completion = min(event.media_position / event.media_duration, 1.0)
    
    watch_time = 0
    if event.event_type == 'play' and event.media_position:
        watch_time = event.media_position
    
    watch_increment = 1 if event.event_type == 'play' else 0
    
    conn.execute("""
        INSERT INTO tv_preferences (
            series_title, season, episode, watch_count, total_watch_time,
            last_watched, first_watched, completion_percentage, preferred_time_of_day
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(series_title, season, episode) DO UPDATE SET
            watch_count = watch_count + ?,
            total_watch_time = total_watch_time + ?,
            last_watched = ?,
            completion_percentage = MAX(completion_percentage, ?),
            preferred_time_of_day = CASE 
                WHEN watch_count < 3 THEN ?
                ELSE preferred_time_of_day 
            END
    """, (
        series_title, event.media_season, event.media_episode,
        watch_increment, watch_time, event_time, event_time, completion, time_of_day,
        # ON CONFLICT updates  
        watch_increment, watch_time, event_time, completion, time_of_day
    ))


async def _update_movie_preferences(conn: sqlite3.Connection, event: MediaEvent, event_time: datetime, time_of_day: str):
    """Update movie preferences based on the event."""
    # Calculate completion percentage
    completion = 0.0
    if event.media_duration and event.media_position:
        completion = min(event.media_position / event.media_duration, 1.0)
    
    watch_time = 0
    if event.event_type == 'play' and event.media_position:
        watch_time = event.media_position
    
    watch_increment = 1 if event.event_type == 'play' else 0
    
    conn.execute("""
        INSERT INTO movie_preferences (
            movie_title, year, watch_count, total_watch_time,
            last_watched, first_watched, completion_percentage, preferred_time_of_day
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(movie_title, year) DO UPDATE SET
            watch_count = watch_count + ?,
            total_watch_time = total_watch_time + ?,
            last_watched = ?,
            completion_percentage = MAX(completion_percentage, ?),
            preferred_time_of_day = CASE 
                WHEN watch_count < 3 THEN ?
                ELSE preferred_time_of_day 
            END
    """, (
        event.media_title, event.media_year, watch_increment, watch_time,
        event_time, event_time, completion, time_of_day,
        # ON CONFLICT updates
        watch_increment, watch_time, event_time, completion, time_of_day
    ))

async def _get_media_stats() -> Dict[str, Any]:
    """Get summary statistics about tracked media consumption."""
    try:
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            # Get basic counts
            cursor = conn.execute("""
                SELECT 
                    media_content_type,
                    COUNT(*) as event_count,
                    COUNT(DISTINCT device_id) as device_count
                FROM media_events 
                GROUP BY media_content_type
            """)
            
            content_stats = {}
            for row in cursor.fetchall():
                content_type, event_count, device_count = row
                content_stats[content_type] = {
                    "events": event_count,
                    "devices": device_count
                }
            
            # Get recent activity  
            cursor = conn.execute("""
                SELECT media_content_type, media_title, timestamp
                FROM media_events 
                WHERE event_type = 'play'
                ORDER BY timestamp DESC 
                LIMIT 10
            """)
            
            recent_activity = []
            for row in cursor.fetchall():
                content_type, title, timestamp = row
                recent_activity.append({
                    "type": content_type,
                    "title": title,
                    "timestamp": timestamp
                })
            
            return {
                "content_stats": content_stats,
                "recent_activity": recent_activity
            }
            
    except Exception as e:
        logger.exception(f"Error getting media stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get media stats: {str(e)}"
        )


def _get_current_time_context() -> str:
    """Get current time of day context."""
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 22:
        return "evening"
    else:
        return "night"


def _get_media_preferences_for_context(limit: int = 20) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get media preferences organized by type for LLM context.
    Returns most recent preferences by last played/watched.
    """
    try:
        db_path = get_db_path()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            
            # Get music preferences - most recent artists
            music_cursor = conn.execute("""
                SELECT artist, album, track_title, play_count, total_play_time,
                       last_played, first_played, skip_count, preferred_time_of_day
                FROM music_preferences 
                WHERE play_count > 0
                ORDER BY last_played DESC
                LIMIT ?
            """, (limit,))
            
            music_preferences = [dict(row) for row in music_cursor.fetchall()]
            
            # Get TV preferences - most recent shows
            tv_cursor = conn.execute("""
                SELECT series_title, season, episode, watch_count, total_watch_time,
                       last_watched, first_watched, completion_percentage, preferred_time_of_day
                FROM tv_preferences 
                WHERE watch_count > 0
                ORDER BY last_watched DESC
                LIMIT ?
            """, (limit,))
            
            tv_preferences = [dict(row) for row in tv_cursor.fetchall()]
            
            # Get movie preferences - most recent movies
            movie_cursor = conn.execute("""
                SELECT movie_title, year, watch_count, total_watch_time,
                       last_watched, first_watched, completion_percentage, preferred_time_of_day
                FROM movie_preferences 
                WHERE watch_count > 0
                ORDER BY last_watched DESC
                LIMIT ?
            """, (limit,))
            
            movie_preferences = [dict(row) for row in movie_cursor.fetchall()]
            
            return {
                "music_preferences": music_preferences,
                "tv_preferences": tv_preferences,
                "movie_preferences": movie_preferences
            }
            
    except Exception as e:
        logger.exception(f"Error getting media preferences: {e}")
        return {
            "music_preferences": [],
            "tv_preferences": [],
            "movie_preferences": []
        }


def _is_media_request(request_text: str) -> bool:
    """
    Determine if a request is asking for media recommendations or playback.
    """
    media_keywords = [
        "play", "music", "song", "artist", "album", "playlist",
        "watch", "movie", "show", "tv", "anime", "series",
        "recommend", "suggestion", "what should i", "something to",
        "crunchyroll", "netflix", "spotify", "apple music"
    ]
    
    request_lower = request_text.lower()
    return any(keyword in request_lower for keyword in media_keywords)


def _get_media_devices_from_config(devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter devices to only include media players.
    """
    media_device_types = [
        "media_player",
        "remote",  # TV remotes, etc.
    ]
    
    media_devices = []
    for device in devices:
        # Check device type or look for media-related keywords in name/description
        device_type = device.get("device_type", "").lower()
        device_name = device.get("name", "").lower()
        
        if (device_type in media_device_types or 
            any(media_word in device_name for media_word in ["tv", "homepod", "speaker", "music", "player"])):
            media_devices.append(device)
    
    return media_devices


def _build_media_context_for_llm(request_text: str, devices: List[Dict[str, Any]], media_types: List[str] = None) -> Dict[str, Any]:
    """
    Build comprehensive context for media recommendation LLM calls.
    """
    preferences = _get_media_preferences_for_context()
    media_devices = _get_media_devices_from_config(devices)
    current_time = _get_current_time_context()
    
    # Filter preferences based on requested media types
    filtered_preferences = {}
    if media_types:
        for media_type in media_types:
            if media_type == "music":
                filtered_preferences["music_preferences"] = preferences.get("music_preferences", [])
            elif media_type == "tv":
                filtered_preferences["tv_preferences"] = preferences.get("tv_preferences", [])
            elif media_type == "movie":
                filtered_preferences["movie_preferences"] = preferences.get("movie_preferences", [])
    else:
        # If no specific types requested, include all
        filtered_preferences = preferences

    return {
        "full_request": request_text,
        "current_time_of_day": current_time,
        "devices": media_devices,
        **filtered_preferences
    }
