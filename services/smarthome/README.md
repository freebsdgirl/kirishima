# Smarthome Microservice

Natural language control for Home Assistant devices. Uses LLM-driven intent detection and action generation — user says "turn on the bedroom lights with something relaxing" and the service figures out which devices, which scenes/effects, and executes via Home Assistant WebSocket API. Runs on `${SMARTHOME_PORT}`.

## Endpoints

### Primary (Actively Used)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/user_request` | Natural language device control — the main endpoint |

### Discovery (Debugging/Utility)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/areas` | List Home Assistant area names |
| GET | `/devices` | List devices (filtered to `ai_assisted` label by default) |
| GET | `/area/{area}/devices` | Devices in a specific area |
| GET | `/device/{device_id}/entities` | Entities for a device with current states |
| GET | `/entity` | List entities (filtered by label) |
| GET | `/entity/{entity_id}` | Entity state and attributes |
| GET | `/populate-devices-json` | Regenerate device/entity metadata snapshot |

### Media Tracking

| Method | Path | Description |
|--------|------|-------------|
| POST | `/media/media_event` | Webhook for HA automations to log media events |
| GET | `/media/media_stats` | Aggregated media consumption statistics |

## How `/user_request` Works

Three-phase LLM pipeline:

### Phase 1: Device Matching
- Load device overrides from `lighting.json` (effects, scenes, notes per device)
- Fetch device list from Home Assistant
- LLM classifies intent: `DEVICE_CONTROL`, `MEDIA_CONTROL`, `MEDIA_RECOMMENDATION`, or `QUERY`
- LLM returns matched device IDs with reasoning

### Phase 2: Context Building
- Fetch matched device entities and current states
- Fetch controller entities (e.g., `input_select.bedroom_scenes`) with available options
- Fetch related devices for context (other lights in same area)
- Build detailed prompt with current states, effects/scenes, time of day

### Phase 3: Action Generation + Execution
- LLM generates Home Assistant service calls as JSON array
- Each action: `{type, domain, service, entity_id, service_data}`
- Execute each via Home Assistant WebSocket API
- Return results with actions, reasoning, status

### Example

Request:
```json
{"full_request": "Turn on the bedroom lights with something relaxing", "name": "Bedroom Lights"}
```

Response:
```json
{
    "actions": [{"type": "call_service", "domain": "input_select", "service": "select_option",
                 "entity_id": "input_select.bedroom_scenes", "service_data": {"option": "Nightlight"}}],
    "reasoning": "Selected Nightlight scene for relaxing bedroom atmosphere",
    "status": "success"
}
```

## Device Override System (`lighting.json`)

11 light devices configured with:
- Custom names and notes (e.g., "keep at 60% or lower")
- Controller entity IDs (`input_select.*_scenes`)
- Effect/scene definitions with descriptions and usage context

Example:
```json
{
    "device_id": "...",
    "name": "Nanoleaf Aurora",
    "notes": "Light tends to be fairly bright, keep at 60% or lower",
    "controller": "input_select.nanoleaf_scenes",
    "effects": [
        {"name": "90s", "description": "pinks and greens", "when_to_use": "daytime, energy"}
    ]
}
```

## Media Tracking System

SQLite-backed media consumption tracking:

- **`media_events`**: Raw event log (play, pause, stop, skip) from HA automations
- **`music_preferences`**: Artist/album/track play counts, skip counts, preferred times
- **`tv_preferences`**: Series watch counts, completion rates
- **`movie_preferences`**: Movie watch counts, completion rates
- **`media_sessions`**: Event grouping into sessions with context

Content type detection: explicit from HA, app-based (Spotify→music, Netflix→tvshow), or metadata-based.

HA automation template in `home_assistant_media_automation.yaml`.

## Home Assistant Integration

All HA communication via **WebSocket API** (not REST):
- Device/area/entity registry queries
- State queries
- Service calls (light.turn_on, input_select.select_option, etc.)
- Authentication via long-lived access token
- Filtering by `ai_assisted` label (configurable)

## File Structure

```
app/
├── app.py                      # FastAPI setup, lifespan, DB init
├── setup.py                    # SQLite schema (5 media tables)
├── util.py                     # ha_ws_call() WebSocket wrapper
├── prompts.py                  # NOT CODE — example prompts/curls (should be docs)
├── lighting.json               # Device overrides with effects/scenes
├── devices.json                # Auto-generated HA device snapshot
├── media_players.json          # Media player mappings (unused)
├── motion.json                 # Motion sensor mappings (unused)
├── routes/
│   ├── request.py              # POST /user_request
│   ├── area.py                 # Area endpoints
│   ├── device.py               # Device endpoints
│   ├── entity.py               # Entity endpoints
│   ├── json.py                 # /populate-devices-json
│   └── media.py                # Media tracking endpoints
└── services/
    ├── request.py              # NLP pipeline: match → context → generate → execute
    ├── area.py                 # HA area/device registry calls
    ├── device.py               # Device filtering, entity retrieval
    ├── entity.py               # Entity state queries
    ├── json.py                 # Device metadata serialization
    └── media.py                # Media event tracking, preference aggregation
```

## Dependencies

- **Home Assistant**: WebSocket API for device control and state queries
- **Proxy service**: LLM inference for device matching and action generation (uses "smarthome" mode)
- **SQLite**: Media consumption tracking

## Known Issues and Recommendations

### Critical Bugs

1. **Infinite recursion in `routes/area.py:29`** — `list_devices_by_area()` calls itself instead of the service function. Will crash on any call.

2. **Duplicate route definitions in `routes/media.py`** — Lines 1-46 and 47-68 define the same endpoints twice. Second version shadows the first and lacks error handling.

3. **Undefined variable in `services/request.py:337`** — `hs_actions` referenced in error handler but not defined in that scope. Should be `hs_data` or the raw response.

### Other Issues

4. **Only checks last action for success** — If 5 actions execute and #3 fails, only #5's result is checked. Should track all failures.

5. **No state validation before execution** — LLM-generated actions aren't validated (entity IDs exist, brightness 0-100, valid colors). Failures only caught at HA execution time.

6. **`media_players.json` and `motion.json` are orphaned** — Loaded by nothing. Either future features or abandoned.

7. **`prompts.py` is documentation, not code** — 214 lines of example curl commands in a .py file. Should be in README or docs/.

8. **No retry logic** — WebSocket calls to HA are fire-and-forget with no retry on transient failures.

9. **Media preferences not used in device control** — Media tracking database exists but isn't consulted during DEVICE_CONTROL or MEDIA_CONTROL intents, only MEDIA_RECOMMENDATION.

### Recommendations

- Fix the three critical bugs immediately
- Add action validation before HA execution
- Track cumulative action success/failure
- Move `prompts.py` content to documentation
- Remove or integrate orphaned JSON configs
- Add retry logic for WebSocket calls
