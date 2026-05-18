#!/usr/bin/env python3
"""Discord webhook integration for AI News Finder notifications."""

import json
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def get_discord_webhook_url() -> Optional[str]:
    """Get Discord webhook URL from environment variable."""
    return os.getenv("DISCORD_WEBHOOK_URL")


def send_notification(
    title: str,
    message: str,
    color: int = 3447003,  # Default blue color
    fields: Optional[list[dict]] = None,
    status: str = "info",
) -> bool:
    """
    Send a notification to Discord via webhook.

    Args:
        title: Embed title
        message: Embed description/message
        color: Embed color (decimal RGB)
        fields: Optional list of field dicts with 'name' and 'value' keys
        status: Status type ('success', 'error', 'info')

    Returns:
        True if successful, False otherwise
    """
    webhook_url = get_discord_webhook_url()
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not set. Skipping Discord notification.")
        return False

    # Color mapping for different statuses
    color_map = {
        "success": 3066993,  # Green
        "error": 15158332,   # Red
        "info": 3447003,     # Blue
        "warning": 16776960, # Yellow
    }
    embed_color = color_map.get(status, color)

    embed = {
        "title": title,
        "description": message,
        "color": embed_color,
    }

    if fields:
        embed["fields"] = fields

    payload = {
        "embeds": [embed],
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        logger.info("Discord notification sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Discord notification: {e}")
        return False


def send_success_notification(
    title: str = "✅ AI News Finder Run Completed",
    message: str = "Daily AI news collection and report generation completed successfully.",
    fields: Optional[list[dict]] = None,
) -> bool:
    """Send a success notification to Discord."""
    return send_notification(title, message, status="success", fields=fields)


def send_error_notification(
    title: str = "❌ AI News Finder Run Failed",
    message: str = "An error occurred during the daily AI news collection.",
    error_details: Optional[str] = None,
) -> bool:
    """Send an error notification to Discord."""
    fields = []
    if error_details:
        fields.append(
            {
                "name": "Error Details",
                "value": error_details[:1024],  # Discord field value limit
                "inline": False,
            }
        )

    return send_notification(title, message, status="error", fields=fields)


def send_report_summary(
    total_stories: int,
    sources_count: int,
    verified_count: int,
    report_file: str = "",
) -> bool:
    """
    Send a summary of the AI news report to Discord.

    Args:
        total_stories: Number of stories in the final report
        sources_count: Number of unique sources used
        verified_count: Number of verified stories (3+ sources)
        report_file: Optional path/name of the report file

    Returns:
        True if successful, False otherwise
    """
    fields = [
        {"name": "📊 Stories Selected", "value": str(total_stories), "inline": True},
        {"name": "📡 Sources Used", "value": str(sources_count), "inline": True},
        {"name": "✅ Verified Stories", "value": str(verified_count), "inline": True},
    ]

    if report_file:
        fields.append(
            {
                "name": "📄 Report File",
                "value": report_file,
                "inline": False,
            }
        )

    return send_notification(
        title="📰 AI News Report Summary",
        message="Daily AI news collection and ranking completed.",
        status="success",
        fields=fields,
    )


if __name__ == "__main__":
    # Test the Discord notifier
    logging.basicConfig(level=logging.INFO)

    # Test success notification
    send_success_notification(
        fields=[
            {"name": "Repository", "value": "news-update", "inline": True},
            {"name": "Branch", "value": "main", "inline": True},
        ]
    )

    # Test report summary
    send_report_summary(
        total_stories=10,
        sources_count=15,
        verified_count=7,
        report_file="report_2026-05-18.html",
    )
