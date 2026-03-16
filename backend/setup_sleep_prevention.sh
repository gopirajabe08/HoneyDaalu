#!/bin/bash
# One-time setup: Allow the backend to prevent/enable Mac sleep without password prompt.
# This adds a sudoers rule so 'sudo pmset disablesleep' works without a password.
#
# Run this ONCE:   sudo bash setup_sleep_prevention.sh

set -e

USER_NAME=$(logname 2>/dev/null || echo "$SUDO_USER")

if [ -z "$USER_NAME" ]; then
    echo "Error: Could not determine username. Run with: sudo bash setup_sleep_prevention.sh"
    exit 1
fi

SUDOERS_FILE="/etc/sudoers.d/intratrading-pmset"

echo "$USER_NAME ALL=(ALL) NOPASSWD: /usr/bin/pmset disablesleep *" > "$SUDOERS_FILE"
chmod 0440 "$SUDOERS_FILE"

# Validate sudoers syntax
if visudo -cf "$SUDOERS_FILE" >/dev/null 2>&1; then
    echo "Done! Sleep prevention configured for user: $USER_NAME"
    echo "The auto-trader can now prevent sleep even with the lid closed."
else
    echo "Error: Invalid sudoers syntax. Removing file."
    rm -f "$SUDOERS_FILE"
    exit 1
fi
