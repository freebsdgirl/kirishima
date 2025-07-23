#!/usr/bin/env python3
"""
Test script for the media tracking functionality.
Simulates various media events to test the database and API.
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8087"

async def test_media_event(client: httpx.AsyncClient, event_data: dict):
    """Send a test media event to the API."""
    print(f"Testing {event_data['event_type']} event for {event_data.get('media_title', 'Unknown')}")
    
    response = await client.post(f"{BASE_URL}/media/media_event", json=event_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success: {result['message']} (Type: {result['content_type']})")
    else:
        print(f"✗ Failed: {response.status_code} - {response.text}")
    
    print()

async def get_media_stats(client: httpx.AsyncClient):
    """Get and display media statistics."""
    print("Getting media statistics...")
    
    response = await client.get(f"{BASE_URL}/media/media_stats")
    
    if response.status_code == 200:
        stats = response.json()
        print("📊 Media Statistics:")
        
        for content_type, data in stats['content_stats'].items():
            print(f"  {content_type.title()}: {data['events']} events from {data['devices']} devices")
        
        print("\n🎵 Recent Activity:")
        for activity in stats['recent_activity'][:5]:  # Show last 5
            print(f"  {activity['type']}: {activity['title']} at {activity['timestamp']}")
    else:
        print(f"✗ Failed to get stats: {response.status_code} - {response.text}")
    
    print()

async def main():
    """Run test scenarios."""
    async with httpx.AsyncClient() as client:
        print("🎬 Testing Media Tracking System\n")
        
        # Test music events
        music_events = [
            {
                "device_id": "media_player.homepod",
                "device_name": "HomePod",
                "app_name": "Music Assistant", 
                "media_content_type": "music",
                "media_title": "Bohemian Rhapsody",
                "media_artist": "Queen",
                "media_album": "A Night at the Opera",
                "media_duration": 355,
                "media_position": 0,
                "event_type": "play",
                "timestamp": datetime.now().isoformat()
            },
            {
                "device_id": "media_player.homepod",
                "device_name": "HomePod",
                "app_name": "Music Assistant",
                "media_content_type": "music", 
                "media_title": "Bohemian Rhapsody",
                "media_artist": "Queen",
                "media_album": "A Night at the Opera",
                "media_duration": 355,
                "media_position": 180,
                "event_type": "pause"
            },
            {
                "device_id": "media_player.homepod",
                "device_name": "HomePod",
                "app_name": "Music Assistant",
                "media_content_type": "music",
                "media_title": "Don't Stop Me Now",
                "media_artist": "Queen", 
                "media_album": "Jazz",
                "media_duration": 210,
                "media_position": 0,
                "event_type": "play"
            }
        ]
        
        # Test TV show events
        tv_events = [
            {
                "device_id": "media_player.apple_tv",
                "device_name": "Apple TV",
                "app_name": "Crunchyroll",
                "media_content_type": "tvshow",
                "media_title": "Attack on Titan",
                "media_series_title": "Attack on Titan",
                "media_season": "4",
                "media_episode": "28",
                "media_duration": 1440,
                "media_position": 0,
                "event_type": "play"
            },
            {
                "device_id": "media_player.apple_tv",
                "device_name": "Apple TV", 
                "app_name": "Crunchyroll",
                "media_content_type": "tvshow",
                "media_title": "Attack on Titan",
                "media_series_title": "Attack on Titan",
                "media_season": "4",
                "media_episode": "28",
                "media_duration": 1440,
                "media_position": 1400,
                "event_type": "stop"
            }
        ]
        
        # Test movie events
        movie_events = [
            {
                "device_id": "media_player.apple_tv",
                "device_name": "Apple TV",
                "app_name": "Apple TV",
                "media_content_type": "movie",
                "media_title": "Inception",
                "media_year": 2010,
                "media_duration": 8880,
                "media_position": 0,
                "event_type": "play"
            }
        ]
        
        # Send all test events
        print("🎵 Testing Music Events:")
        for event in music_events:
            await test_media_event(client, event)
        
        print("📺 Testing TV Show Events:")
        for event in tv_events:
            await test_media_event(client, event)
        
        print("🎬 Testing Movie Events:")
        for event in movie_events:
            await test_media_event(client, event)
        
        # Get final statistics
        await get_media_stats(client)

if __name__ == "__main__":
    asyncio.run(main())
