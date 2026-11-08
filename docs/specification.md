# YAXIN AI
## Technical Development Specification

**Version:** 1.0  
**Date:** 8 November 2026  
**Product:** AI-Powered Voice Assistant and Digital Life Agent  
**Primary Market:** Azerbaijan  
**Primary Language:** Azerbaijani  
**Platform:** Android-first Flutter application  
**Backend:** Python / FastAPI

---

# 1. Executive Summary

YAXIN AI is an Azerbaijani voice-first AI agent designed to simplify digital interactions.
The application allows users to perform selected digital tasks through natural language commands instead of navigating complex mobile interfaces.

The primary goal is Digital Inclusion.

The MVP focuses on three core capabilities:
1. Voice Contact Agent.
2. Smart Reminder Agent.
3. AI Digital Shield.

# 2. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Azerbaijani voice input | Critical |
| FR-02 | Speech-to-text conversion | Critical |
| FR-03 | Intent detection | Critical |
| FR-04 | Local contact access | Critical |
| FR-05 | Contact matching | Critical |
| FR-06 | Call confirmation | Critical |
| FR-07 | Reminder creation | Critical |
| FR-08 | Local notifications | High |
| FR-09 | User-provided message analysis | High |
| FR-10 | Voice response | High |
| FR-11 | User preferences | Medium |

# 3. MVP Scope

### Included
- Voice assistant & Azerbaijani speech recognition
- Intent classification & LangGraph agent workflow
- Local contact search & call confirmation
- Reminder creation & notifications
- Suspicious message analysis (Digital Shield)

### Excluded
- Real bank transfers & real Wolt orders (simulated/blocked in MVP)
- Automatic SMS reading, WhatsApp access, GPS tracking, call history access
- Automatic medical decisions

