#!/bin/bash
# TOTP Automation Handler for IB Gateway
# This script monitors for the 2FA dialog and automatically enters the TOTP code
# It runs for the lifetime of the container to handle re-authentication events
# Supports TRADING_MODE=both (live + paper sessions with separate 2FA dialogs)

# Check if TWOFACTOR_CODE is set
if [ -z "$TWOFACTOR_CODE" ]; then
    echo "[TOTP] TWOFACTOR_CODE not set, TOTP automation disabled"
    exit 0
fi

# Track window IDs we've already handled
declare -A handled_windows

# Function to generate TOTP code
generate_totp() {
    oathtool --totp --base32 "$TWOFACTOR_CODE"
}

# Function to get all unhandled 2FA dialog window IDs
get_2fa_windows() {
    local windows
    windows=$(xdotool search --name "Second Factor Authentication" 2>/dev/null)
    local unhandled=""
    for wid in $windows; do
        if [ -z "${handled_windows[$wid]}" ]; then
            unhandled+="$wid "
        fi
    done
    echo "$unhandled"
}

# Function to enter TOTP code into a specific window
enter_totp_code() {
    local window_id="$1"
    local code
    code=$(generate_totp)

    echo "[TOTP] Generated TOTP code, entering into window $window_id..."

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

    echo "[TOTP] Code entered and submitted for window $window_id"
    return 0
}

# Main monitoring loop
echo "[TOTP] TOTP automation enabled, monitoring for 2FA dialog..."

# Wait for X server to be ready
while ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
    sleep 1
done

# Monitor for 2FA dialog indefinitely
while true; do
    windows=$(get_2fa_windows)
    if [ -n "$windows" ]; then
        for window_id in $windows; do
            echo "[TOTP] 2FA dialog detected (window $window_id)!"
            sleep 2  # Wait for dialog to fully render

            if enter_totp_code "$window_id"; then
                echo "[TOTP] TOTP automation completed successfully for window $window_id"
                handled_windows[$window_id]=1
            else
                sleep 3
            fi
        done
        # Brief pause then check again for more dialogs (e.g. paper session)
        sleep 5
        # Clear handled windows once all dialogs are gone
        if [ -z "$(xdotool search --name "Second Factor Authentication" 2>/dev/null)" ]; then
            handled_windows=()
        fi
    fi

    sleep 5
done
