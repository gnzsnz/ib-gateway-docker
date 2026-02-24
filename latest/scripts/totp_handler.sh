#!/bin/bash
# TOTP Automation Handler for IB Gateway
# This script monitors for the 2FA dialog and automatically enters the TOTP code

set -e

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
        # Focus the window (use windowfocus instead of windowactivate for Xvfb)
        xdotool windowfocus "$window_id"
        sleep 0.5

        # Enter the code
        xdotool type "$code"
        sleep 0.5

        # Try multiple methods to submit
        # Method 1: Press Enter
        xdotool key Return
        sleep 0.2

        # Method 2: Tab to button and press Space
        xdotool key Tab
        sleep 0.2
        xdotool key space
        sleep 0.2

        # Method 3: Click OK button (right side of dialog)
        xdotool mousemove --window "$window_id" 250 110
        sleep 0.2
        xdotool click 1

        echo "[TOTP] TOTP code entered and submitted (Enter+Tab+Click)"
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

# Monitor for 2FA dialog
attempt=0
max_attempts=60  # 5 minutes (60 * 5 seconds)

while [ $attempt -lt $max_attempts ]; do
    if check_2fa_dialog >/dev/null; then
        echo "[TOTP] 2FA dialog detected!"
        sleep 2  # Wait for dialog to fully render

        if enter_totp_code; then
            echo "[TOTP] TOTP automation completed successfully"
            exit 0
        fi

        # If entry failed, try again
        sleep 3
    fi

    sleep 5
    attempt=$((attempt + 1))
done

echo "[TOTP] Monitoring timeout reached, exiting"
exit 0
