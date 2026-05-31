#!/usr/bin/env sh

. ./.env

strava_token() {
  curl -s -X POST https://www.strava.com/oauth/token \
    -d client_id="${CLIENT_ID}" \
    -d client_secret="${CLIENT_SECRET}" \
    -d grant_type=refresh_token \
    -d refresh_token="${REFRESH_TOKEN}" \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4
}

echo "$(strava_token)"
