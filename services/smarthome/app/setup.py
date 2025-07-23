"""
Database setup for smarthome service media history tracking.
Creates tables for tracking music, TV shows, movies, and other media consumption.
"""
import sqlite3
import json
import os
from typing import Dict, Any

def get_db_path() -> str:
    """Get database path from config.json"""
    config_path = '/app/config/config.json'
    with open(config_path) as f:
        config = json.load(f)
    return config['db']['smarthome']

def setup_database() -> None:
    """Initialize the smarthome media history database with all required tables."""
    db_path = get_db_path()
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Media events table - stores all media activity
        conn.execute("""
            CREATE TABLE IF NOT EXISTS media_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                device_id TEXT NOT NULL,
                device_name TEXT,
                app_name TEXT,
                media_content_type TEXT,  -- 'music', 'tvshow', 'movie', 'podcast', etc.
                
                -- Common fields
                media_title TEXT,
                media_duration INTEGER,  -- in seconds
                media_position INTEGER,  -- current position in seconds
                
                -- Music specific
                media_artist TEXT,
                media_album TEXT,
                media_album_artist TEXT,
                media_track INTEGER,
                
                -- TV/Movie specific  
                media_series_title TEXT,
                media_season TEXT,
                media_episode TEXT,
                media_year INTEGER,
                
                -- Event metadata
                event_type TEXT NOT NULL,  -- 'play', 'pause', 'stop', 'skip', 'seek'
                raw_attributes TEXT,  -- JSON dump of all attributes for debugging
                
                -- Context when event occurred
                time_of_day TEXT,  -- 'morning', 'afternoon', 'evening', 'night'
                other_devices_active TEXT,  -- JSON list of other active devices
                
                UNIQUE(timestamp, device_id, event_type)
            )
        """)
        
        # Music preferences derived table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS music_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist TEXT NOT NULL,
                album TEXT,
                track_title TEXT,
                play_count INTEGER DEFAULT 1,
                total_play_time INTEGER DEFAULT 0,  -- total seconds listened
                last_played DATETIME,
                first_played DATETIME,
                skip_count INTEGER DEFAULT 0,
                preferred_time_of_day TEXT,  -- when user most often plays this
                
                UNIQUE(artist, album, track_title)
            )
        """)
        
        # TV/Anime preferences derived table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tv_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_title TEXT NOT NULL,
                season TEXT,
                episode TEXT,
                watch_count INTEGER DEFAULT 1,
                total_watch_time INTEGER DEFAULT 0,
                last_watched DATETIME,
                first_watched DATETIME,
                completion_percentage REAL,  -- how much of episode was watched
                preferred_time_of_day TEXT,
                
                UNIQUE(series_title, season, episode)
            )
        """)
        
        # Movie preferences derived table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movie_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_title TEXT NOT NULL,
                year INTEGER,
                watch_count INTEGER DEFAULT 1,
                total_watch_time INTEGER DEFAULT 0,
                last_watched DATETIME,
                first_watched DATETIME,
                completion_percentage REAL,
                preferred_time_of_day TEXT,
                
                UNIQUE(movie_title, year)
            )
        """)
        
        # Listening/watching sessions - groups events into sessions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS media_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_start DATETIME NOT NULL,
                session_end DATETIME,
                device_id TEXT NOT NULL,
                media_type TEXT NOT NULL,  -- 'music', 'tv', 'movie'
                primary_content TEXT,  -- main thing consumed (artist, show, movie)
                total_items INTEGER DEFAULT 0,  -- songs played, episodes watched
                total_duration INTEGER DEFAULT 0,  -- total session time
                context_summary TEXT,  -- brief description of what happened
                
                -- Session context
                time_of_day_start TEXT,
                time_of_day_end TEXT,
                lighting_state TEXT  -- snapshot of lighting when session started
            )
        """)
        
        # Indexes for better query performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_sessions_start ON media_sessions(session_start)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_sessions_device ON media_sessions(device_id, session_start)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_events_timestamp ON media_events(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_events_device ON media_events(device_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_events_type ON media_events(media_content_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_events_app ON media_events(app_name)")
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_music_artist ON music_preferences(artist)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_music_last_played ON music_preferences(last_played)")
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tv_series ON tv_preferences(series_title)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tv_last_watched ON tv_preferences(last_watched)")
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_movie_title ON movie_preferences(movie_title)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_movie_last_watched ON movie_preferences(last_watched)")
        
        conn.commit()

def verify_database() -> bool:
    """Verify that the database was created successfully and has all expected tables."""
    try:
        db_path = get_db_path()
        
        if not os.path.exists(db_path):
            return False
            
        with sqlite3.connect(db_path) as conn:
            # Check that all expected tables exist
            expected_tables = [
                'media_events',
                'music_preferences', 
                'tv_preferences',
                'movie_preferences',
                'media_sessions'
            ]
            
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            
            existing_tables = {row[0] for row in cursor.fetchall()}
            
            missing_tables = set(expected_tables) - existing_tables
            if missing_tables:
                print(f"Missing tables: {missing_tables}")
                return False
                
            return True
            
    except Exception as e:
        print(f"Database verification failed: {e}")
        return False

if __name__ == "__main__":
    setup_database()
    if verify_database():
        print("✓ Smarthome database setup completed successfully")
    else:
        print("✗ Database setup failed verification")
