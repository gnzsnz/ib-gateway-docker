#!/bin/bash
# TOTP Automation Handler for IB Gateway
# This script monitors for the 2FA dialog and automatically enters the TOTP code
# It runs for the lifetime of the container to handle re-authentication events

# Check if TWOFACTOR_CODE is set
if [ -z "$TWOFACTOR_CODE" ]; then
    echo "[TOTP] TWOFACTOR_CODE not set, TOTP automation disabled"
    exit 0
fi

# Function to generate TOTP code
generate_totp() {
    oathtool --totp --base32 "$TWOFACTOR_CODE"
}

# Function to check if 2FA dialog is present
check_2fa_dialog() {
    xdotool search --name "Second Factor Authentication" 2>/dev/null
}

# Function to enter TOTP code
enter_totp_code() {
    local code
    code=$(generate_totp)

    echo "[TOTP] Generated TOTP code, entering..."

    # Find the 2FA window
    local window_id
    window_id=$(xdotool search --name "Second Factor Authentication" | head -1)

    if [ -n "$window_id" ]; then
        # Focus the window
        xdotool windowfocus "$window_id"
        sleep 1

        # Click in the input field to ensure focus
        xdotool mousemove --window "$window_id" 150 75
        xdotool click 1
        sleep 0.5

        # Clear any existing text
        xdotool key ctrl+a
        sleep 0.2

        # Type the code
        xdotool type --delay 100 "$code"
        sleep 1

        # Submit
        xdotool key Return

        echo "[TOTP] Code entered and submitted"
        return 0
    else
        echo "[TOTP] 2FA window not found"
        return 1
    fi
}

# Main monitoring loop
echo "[TOTP] TOTP automation enabled, monitoring for 2FA dialog..."

# Wait for X server to be ready
while ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
    sleep 1
done

# Monitor for 2FA dialog indefinitely
while true; do
    if check_2fa_dialog >/dev/null 2>&1; then
        echo "[TOTP] 2FA dialog detected!"
        sleep 2  # Wait for dialog to fully render

        if enter_totp_code; then
            echo "[TOTP] TOTP automation completed successfully"
            # Cooldown to avoid re-triggering on the same dialog
            sleep 30
        else
            # If entry failed, retry shortly
            sleep 3
        fi
    fi

    sleep 5
done
