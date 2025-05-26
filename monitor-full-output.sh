#!/bin/bash

NTFY_TOPIC="discord-bot-rpi"

journalctl -fu discordbot.service --no-pager |
while read -r line; do
	if [[ -n "$line" ]]; then
		/usr/bin/ntfy publish "$NTFY_TOPIC" -m "$line"
	fi
done
