## Memory & Context Pipeline

- **Long-term: Agentic memory retrieval, summarization, and contextual relevance pipeline**
	- Move beyond basic keyword search for memories.
	- Planner agent orchestrates contextual queries based on current task.
	- Retrieve, cluster, and rank relevant memories using embeddings or LLM-based scoring.
	- Curate and summarize only the best, most relevant memories for context.
	- Long-term architectural improvement; focus on design and interface sketches for now.
## Architecture & Service Design

- **Slam broker design: Handler interfaces and sync/async abstraction**
	- Design handler interfaces for Slam broker to support both blocking (MVP) and non-blocking (future) request patterns.
	- Dual endpoints: JSON requests and natural language (parsed, fallback to LLM).
	- Start with blocking-only; keep async/non-blocking in mind for future.
	- Clean abstraction layer between broker and service handlers to avoid sync-only lock-in.
	- Future: support callbacks, websockets, or polling for async.
	- Need concrete examples of handler interface patterns for this evolution.
## Reminders & Habit Integration

- **Integrate stickynotes with Habitica tasks (dailies, to-dos)**
	- Map Habitica tasks to stickynotes; surface reminders contextually during agent interactions.
	- Completing a Habitica task resolves/silences its stickynote.
	- Unfinished Habitica items generate stickynotes with custom triggers ("before lunch," "after 4pm," etc.).
	- Goal: bridge gentle, neurodivergence-friendly persistence with Habitica’s gamified accountability.
## Notifications System & Courier Service

- **Extract notifications logic from brain and stand up the courier service**
	- Move all notification logic (user alerts, channel fallback, TTS triggers) from brain to a dedicated courier service.
	- Courier handles intake, delivery, and routing for notifications and webhooks (user, system, external integrations).
	- Brain only reasons about notifications; courier does delivery and keeps API clean.
	- Improves modularity and reduces glue code in brain.

- **Refine and test notifications system with assistant-delivered phrasing**
	- Ensure all notifications (TTS, iMessage, Discord) are delivered in the assistant’s own voice, not raw system output.
	- Simulate/test: assistant rephrases tool output into natural, context-sensitive delivery.
	- Maintains continuity and Kirishima’s brand/tone in all notifications.
	- Implement and test with simulated payloads for each channel.
## GitHub Integration

- **Implement GitHub issue comment polling (as fallback to webhooks)**
	- Poll /repos/:owner/:repo/issues/comments to detect new comments.
	- Use ‘since’ parameter to minimize data transfer.
	- Track processed comment IDs/timestamps to avoid duplicates.
	- Trigger agent response logic on new comments.
	- Document API rate limits and caveats.
	- Polling is a stopgap; prefer webhooks if feasible in future.
## Smarthome Device Integrations

- **Enable agent to give Alexa commands for unsupported devices (window fan, Furbo)**
	- Allow agent to issue Alexa voice/API commands for devices not exposed to Home Assistant (window fan, Furbo dog camera).
	- Bridge Alexa-only devices for agent-driven routines and ad hoc commands.
	- Deliverable: Reliable agent-to-Alexa command flow, documented approach.

- **Integrate Pura diffuser sensors and controls into routines**
	- Query Pura fragrance levels, notify when running low, use sensors as triggers.
	- Enable agent to turn diffusers on/off as part of automations or on demand.
	- Objective: Seamless, context-aware fragrance management and device control for flexible routines.

- **Enable agent to control Home Assistant media players (MusicAssistant, Apple Music, Sonos, HomePod, Apple TV)**
	- Full read-write control: play, pause, next, previous, volume, mute for all linked devices.
	- Select tracks, albums, artists from Apple Music via MusicAssistant.
	- Targeted playback across multiple devices.
	- Handle/report errors for flaky integrations.
	- Playlist support is pending/future enhancement.
# TODO List

This file collects ideas, future features, and low-priority tickets moved from GitHub issues. Each entry includes the original ticket number and a summary.

---

## Integrations / Automation

- **Integrate Weather and Forecast Data for Contextual Automation**
	- Pull current weather and forecast from Home Assistant sensors.
	- Use weather context for lighting decisions (and future automations).
	- Surface weather data for scene/effect selection (overcast, rain, daylight, etc).
	- Design for future adaptive, environment-aware routines.

- **Integrate Media Player Status for Context-Aware Lighting**
	- Query Home Assistant for media player states (e.g., is music playing, what’s active).
	- Use playback context to inform lighting scene/effect selection.
	- Only trigger music-related scenes if audio is actually playing.
	- Lay groundwork for future audio-driven automations.

## Contextual Sensors & Data Integration

- **Integrate Power Monitoring for Device State Awareness**
	- Read power switch states and power draw from Home Assistant.
	- Infer device state (e.g., monitor on/off) for smarter scene logic.
	- Foundation for richer automation and state inference.

- **Integrate Sleep and Routine Data for Smarter Automations**
	- Access sleep/routine data to adjust lighting and automation triggers.
	- Respect sleep cycles and scheduled routines.
	- Foundation for neurodivergent-friendly automations.

- **Integrate Presence and Location Awareness**
	- Use presence/location sensors to determine who is home and which rooms are occupied.
	- Enable room-level and person-specific automations.

- **Integrate Calendar Events for Contextual Automation**
	- Access calendar data (Google Calendar, etc.) via Home Assistant.
	- Use events to inform lighting, scenes, and automations.
	- Enable time- and event-aware routines.

- **Integrate Environmental Sensors (Temp, Humidity, Air Quality)**
	- Read temperature, humidity, and air quality data from Home Assistant.
	- Use sensor data for comfort, wellness, and adaptive automations.
