#!/bin/bash
# Debug script to probe EdgeSwitch API endpoints

if [ $# -ne 3 ]; then
    echo "Usage: $0 <host> <username> <password>"
    echo "Example: $0 192.168.1.1 ubnt password123"
    exit 1
fi

HOST="$1"
USERNAME="$2"
PASSWORD="$3"
BASE_URL="https://${HOST}"
COOKIE_FILE="/tmp/edgeswitch_cookies.txt"

# Clean up old cookies
rm -f "$COOKIE_FILE"

echo ""
echo "============================================================"
echo "Probing EdgeSwitch at ${BASE_URL}"
echo "============================================================"
echo ""

# Step 1: Basic connectivity
echo "[1] Testing basic connectivity..."
RESPONSE=$(curl -sk -o /dev/null -w "%{http_code}" "${BASE_URL}/")
echo "    GET / -> HTTP $RESPONSE"

# Step 2: Get the login page and check what's there
echo ""
echo "[2] Checking login page structure..."
curl -sk "${BASE_URL}/" > /tmp/edgeswitch_login.html 2>/dev/null
echo "    Page size: $(wc -c < /tmp/edgeswitch_login.html) bytes"

if grep -qi "lua" /tmp/edgeswitch_login.html; then
    echo "    Detected: Lua-based interface"
fi
if grep -qi "angular" /tmp/edgeswitch_login.html; then
    echo "    Detected: Angular-based interface"
fi
if grep -qi "api" /tmp/edgeswitch_login.html; then
    echo "    Detected: API references"
fi

# Step 3: Try login endpoints
echo ""
echo "[3] Testing login endpoints..."

# JSON API login attempts
echo "    Trying JSON API logins..."
for endpoint in "/api/v1.0/user/login" "/api/v1/user/login" "/api/auth" "/api/auth/login"; do
    RESPONSE=$(curl -sk -X POST "${BASE_URL}${endpoint}" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}" \
        -c "$COOKIE_FILE" -b "$COOKIE_FILE" \
        -w "\n%{http_code}" 2>/dev/null)
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    echo "    POST ${endpoint} -> HTTP ${HTTP_CODE}"
    if [ "$HTTP_CODE" = "200" ]; then
        echo "        Response: ${BODY:0:200}"
    fi
done

# Form-based login attempts
echo ""
echo "    Trying form-based logins..."
for endpoint in "/htdocs/login/login.lua" "/login.cgi"; do
    RESPONSE=$(curl -sk -X POST "${BASE_URL}${endpoint}" \
        -d "username=${USERNAME}&password=${PASSWORD}" \
        -c "$COOKIE_FILE" -b "$COOKIE_FILE" \
        -w "\n%{http_code}" 2>/dev/null)
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    echo "    POST ${endpoint} -> HTTP ${HTTP_CODE}"
    if [ "$HTTP_CODE" = "200" ]; then
        if echo "$BODY" | grep -qi "logout\|dashboard\|success"; then
            echo "        Login appears SUCCESSFUL!"
        fi
        echo "        Response size: ${#BODY} bytes"
    fi
done

# Step 4: Probe API endpoints
echo ""
echo "[4] Probing API endpoints (with cookies)..."

for endpoint in "/api/v1.0/system" "/api/v1/system" "/api/v1.0/interfaces" "/api/v1.0/ports" "/api/v1.0/poe" \
                "/htdocs/pages/base/dashboard.lsp" "/htdocs/pages/switching/port_summary.lsp" \
                "/htdocs/pages/poe/poe_status.lsp" "/manage" "/manage/api/switch" "/manage/switch"; do
    RESPONSE=$(curl -sk "${BASE_URL}${endpoint}" \
        -b "$COOKIE_FILE" \
        -w "\n%{http_code}" 2>/dev/null)
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    SIZE=${#BODY}
    echo "    GET ${endpoint} -> HTTP ${HTTP_CODE} (${SIZE} bytes)"
done

# Step 5: Show cookies
echo ""
echo "[5] Session cookies:"
if [ -f "$COOKIE_FILE" ]; then
    cat "$COOKIE_FILE"
else
    echo "    No cookies saved"
fi

# Step 6: Check for EdgeOS-style endpoints (some EdgeSwitch use similar)
echo ""
echo "[6] Checking EdgeOS-style endpoints..."
for endpoint in "/api/edge/data.json" "/api/edge/get.json" "/api/get"; do
    RESPONSE=$(curl -sk "${BASE_URL}${endpoint}" \
        -b "$COOKIE_FILE" \
        -w "\n%{http_code}" 2>/dev/null)
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    echo "    GET ${endpoint} -> HTTP ${HTTP_CODE}"
done

echo ""
echo "============================================================"
echo "Debug complete. Share this output to fix the integration."
echo "============================================================"
