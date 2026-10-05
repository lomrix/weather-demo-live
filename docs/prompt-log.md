# Prompt log

These entries describe two real events from 1 October 2026. They were written on 5 October 2026.

## 1. API identification correction

> Before making the request, ask me for genuine contact information
> or a project URL for the User-Agent. Do not invent one. Use the
> same identifier in the application and this test. Treat this as
> an API connectivity check, not proof that the webpage shows
> tomorrow’s forecast correctly.

The proposed MET request used only “local development” as contact information. The user asked the agent to request genuine contact information or a project URL, and to use the same identifier for the application and the test.

The fallback was removed. `MET_USER_AGENT` became required. The user's actual contact information is not recorded here.

## 2. Forecast caching correction

> Correct only the forecast caching in server.py. Respect MET’s
> Expires header and use its Last-Modified value for conditional
> requests after expiry. Handle HTTP 304 by retaining the cached
> forecast. Do not make a live request yet. Explain the change.

The server initially cached forecasts for a fixed ten minutes. The user asked the agent to respect `Expires`, send `If-Modified-Since` using `Last-Modified`, and retain cached data on HTTP 304.

The saved implementation was inspected with Codex assistant help. The agent reported passing mock checks, but their raw output was not independently inspected.

## Separate forecast comparison

One user-run forecast was compared with saved real API data with Codex assistant help. The displayed temperature, wind, condition, sampled low/high, and daily precipitation matched that response.

## Remaining issues

- Incomplete-day handling.
- Stale display after a failed refresh.
- An unexplained connection-aborted error.
