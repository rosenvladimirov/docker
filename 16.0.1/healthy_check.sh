#!/bin/bash

RESTORE_LOCK_FILE="$HOME/.restore.lock"
LIVENESS_PROBE_URL="http://localhost:8069"
LIVENESS_PROBE_FILE="$HOME/.liveness-probe-session"

# Succeed if a restore process is in progress to prevent interruption
[ -f "$RESTORE_LOCK_FILE" ] && exit 0

ensure_odoo_is_running()
{
    if [ $? -gt 0 ]; then
        # Odoo is down or does not respond
        echo "ERROR: No connection to \"${LIVENESS_PROBE_URL}\"!"
        exit 1
    fi
}

# Use this method to reliably get a session cookie
initialize_session()
{
    SESSION_COOKIE="$1"

    [ -n "$SESSION_COOKIE" ] && CURL_SESSION_ARG=(--header "cookie: session_id=$SESSION_COOKIE")

    SESSION_COOKIE="$(
        curl "${LIVENESS_PROBE_URL}/web/database/selector" \
            "${CURL_SESSION_ARG[@]}" \
            --silent \
            --cookie-jar - \
            --output /dev/null \
            | grep 'session_id' \
            | sed -e 's/^.*session_id.//g' \
            | sed -e 's/[ \t].*$//g'
    )"

    ensure_odoo_is_running

    if [ -z "$SESSION_COOKIE" ]; then
        echo "ERROR: Could not get session cookie!"
        exit 1
    else
        echo -n "$SESSION_COOKIE" > "$LIVENESS_PROBE_FILE"
        exit 0
    fi
}

# If there is already a liveness probe session use that one
if [ -f "$LIVENESS_PROBE_FILE" ]; then
    # Get existing session
    SESSION_COOKIE="$( cat $LIVENESS_PROBE_FILE )"

    RESPONSE="$(
        curl "${LIVENESS_PROBE_URL}/web/login" \
            --silent \
            --head \
            --header "cookie: session_id=$SESSION_COOKIE"
    )"

    ensure_odoo_is_running

    HTTP_STATUS_CODE="$( echo "${RESPONSE[@]}" | head -1 | awk '{print $2}' )"
    RESPONSE_SESSION_COOKIE="$(
        echo "${RESPONSE[@]}" \
        | grep "session_id=" \
        | sed -e 's/^.*session_id=//g' \
        | sed -e 's/;.*$//g'
    )"

    if [ -n "$RESPONSE_SESSION_COOKIE" ] && [ "$RESPONSE_SESSION_COOKIE" != "$SESSION_COOKIE" ]; then
        echo "$RESPONSE_SESSION_COOKIE" > "$LIVENESS_PROBE_FILE"
        export SESSION_COOKIE="$RESPONSE_SESSION_COOKIE"
    fi

    if [ $HTTP_STATUS_CODE -ge 200 ] && [ $HTTP_STATUS_CODE -le 299 ]; then
        # That's what we wanna see!
        exit 0
    elif [ $HTTP_STATUS_CODE -ge 300 ] && [ $HTTP_STATUS_CODE -le 399 ]; then
        # Get the URL where we are redirected to
        REDIRECTION_URL="$(
            echo "${RESPONSE[@]}" \
            | grep "Location:" \
            | sed -e "s/^.*${LIVENESS_PROBE_URL}//g"
        )"

        # If there's no database in the system yet, we're getting forwarded to the database selector
        if [ "$REDIRECTION_URL" = "/web/database/selector" ]; then
            initialize_session "$SESSION_COOKIE"
        fi
    elif [ $HTTP_STATUS_CODE -ge 400 ] && [ $HTTP_STATUS_CODE -le 499 ]; then
        initialize_session "$SESSION_COOKIE"
    else
        # It seems there is an internal server error (5XX)
        echo "ERROR: Liveness probe failed!"
        echo "HTTP status code: $HTTP_STATUS_CODE"
        echo "HTTP session cookie: $SESSION_COOKIE"
        echo "HTTP headers:"
        echo "${RESPONSE[@]}"

        exit 1
    fi
else
    initialize_session
fi