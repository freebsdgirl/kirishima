# Divoom Update Endpoint: Architectural Overview

## Overview
This document describes the architecture and flow of the `/divoom` endpoint implemented in the Brain service. The endpoint coordinates between multiple microservices to generate and display an emoji on a Divoom device based on a user's message history.

---

## Flow Summary
1. **Request Initiation**
    - A POST request is made to `/divoom` with a `user_id` query parameter.
2. **Message Retrieval**
    - The Brain service queries the Ledger service to fetch the user's message history.
3. **Message Processing**
    - Messages are sanitized and transformed for downstream processing.
4. **LLM Emoji Generation**
    - The processed messages are sent to the Proxy service, which interacts with a language model (LLM) to generate an emoji response.
5. **Divoom Device Update**
    - The generated emoji is sent to the Divoom device for display.
6. **Response**
    - The endpoint returns the emoji response from the Proxy service.

---

## Services Involved
- **Brain**: Central orchestrator. Handles API requests, message processing, and coordination between services.
- **Ledger**: Stores and serves user message histories.
- **Proxy**: Acts as a gateway to the LLM, generating emoji responses based on message context.
- **Divoom Device**: Receives and displays the emoji.

---

## Detailed Flow
1. **API Call**
    - The client sends a POST request to `/divoom` with a `user_id`.
2. **Ledger Service Query**
    - Brain uses Consul service discovery to locate the Ledger service.
    - It requests the message history for the given user.
    - If no messages are found, a 404 error is returned.
3. **Message Preparation**
    - Each message is assigned a role (`user` or `assistant`) and sanitized.
    - Messages are packaged into a `DivoomRequest` object with LLM parameters (model, temperature, max_tokens).
4. **Proxy Service Call**
    - The request is sent to the Proxy service's `/divoom` endpoint.
    - Proxy forwards the request to the LLM, which generates an emoji response.
    - The response is validated and parsed.
5. **Divoom Device Update**
    - The emoji is sent to the Divoom device via an HTTP POST to its API.
    - If the device update fails, an error is returned.
6. **Final Response**
    - The endpoint returns the emoji response to the client.

---

## Error Handling
- If any service is unreachable or returns an error, the endpoint responds with an appropriate HTTP error code and message.
- If no emoji is generated, a 404 error is returned.

---

## Diagram
```
Client → Brain (/divoom) → Ledger (messages) → Brain (sanitize) → Proxy (LLM) → Brain → Divoom Device
```

---

## Key Points
- The Brain service acts as the central coordinator.
- All LLM interactions are routed through the Proxy service.
- The system is modular and each service is responsible for a specific domain.
- Robust error handling ensures clear feedback to the client.

---

## Extensibility
- The architecture allows for easy integration of new devices or message sources by extending the Brain service and updating service discovery/configuration.

