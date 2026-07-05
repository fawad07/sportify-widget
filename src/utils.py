"""Utility functions for the widget"""

from datetime import datetime


def truncate_text(text: str, max_length: int = 20) -> str:
    """Truncate text if too long"""
    if len(text) > max_length:
        return text[:max_length] + '...'
    return text


def format_event_time(iso_timestamp: str) -> str:
    """Format an ISO timestamp (e.g. '2026-07-05T18:00Z') as a local
    date/time for display; falls back to the raw string."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.astimezone().strftime('%b %d, %I:%M %p')
    except ValueError:
        return iso_timestamp
