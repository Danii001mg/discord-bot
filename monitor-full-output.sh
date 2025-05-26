#!/bin/bash

NTFY_TOPIC="discord-bot-rpi"

journalctl -fu discordbot.service --no-pager |
while read -r line; do
	if [[ -n "$line" && "$line" != *"yt_dlp"* && "$line" != *"jsinterp.py"* ]]; then
		/usr/bin/ntfy publish "$NTFY_TOPIC" "$line"
	fi
done
