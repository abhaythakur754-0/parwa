"""
Jarvis Manager — The Loop-Whole Architecture

Jarvis is NOT a chatbot. Jarvis is a MANAGER/MONITOR that:

  1. MONITORS all variant pipelines in real-time
  2. INTERVENES when variants produce low-quality responses
  3. CORRECTS errors by sending feedback to variants
  4. ESCALATES to humans when needed
  5. NOTIFIES clients via the Notification CRM
  6. COMMUNICATES with clients directly (OpenClaw-inspired action-first)
  7. Has COMPLETE AWARENESS of all system state

Architecture (Loop-Whole):
  ┌─────────────────────────────────────────────────────┐
  │                    JARVIS MANAGER                    │
  │                                                     │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
  │  │ Monitor  │  │ Intervene│  │ Notify   │         │
  │  │          │  │          │  │          │         │
  │  │ Watches  │  │ Fixes    │  │ Alerts   │         │
  │  │ variants │→ │ errors   │→ │ clients  │         │
  │  └──────────┘  └──────────┘  └──────────┘         │
  │       ↑                             │              │
  │       │         ┌──────────┐       │              │
  │       └─────────│ Learn    │←──────┘              │
  │                 │          │                      │
  │                 │ Knowledge│                      │
  │                 │ Base     │                      │
  │                 └──────────┘                      │
  └─────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
  ┌─────────────┐    ┌──────────────┐
  │  VARIANTS   │    │   CLIENTS    │
  │ (Mini/Pro/  │    │ (Dashboard   │
  │  High)      │    │  + Chat)     │
  └─────────────┘    └──────────────┘

OpenClaw-Inspired Design:
  - Action-first: Jarvis doesn't just observe, it ACTS
  - Multi-channel: Can communicate via chat, voice, email, notification
  - Self-healing: Detects and fixes variant errors
  - Tool-use native: Can call any API, trigger any action
  - MCP (Model Context Protocol): Has complete system awareness
"""

from app.services.jarvis_manager.monitor import JarvisMonitor
from app.services.jarvis_manager.manager import JarvisManager
from app.services.jarvis_manager.intervention import JarvisIntervention

__all__ = [
    "JarvisMonitor",
    "JarvisManager",
    "JarvisIntervention",
]
