# data/

## trackers.json: licence and attribution

`trackers.json` is derived from **DuckDuckGo Tracker Radar**
(https://github.com/duckduckgo/tracker-radar, file `build-data/generated/domain_map.json`),
Copyright 2020 Duck Duck Go, Inc.

- Licence: **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**,
  https://creativecommons.org/licenses/by-nc-sa/4.0/
- Changes made: reduced to a plain `domain -> company display name` map (all other fields removed).
- Share-alike: this derived file is shared under the same CC BY-NC-SA 4.0 licence.
- Non-commercial: used here for a non-commercial hackathon project. Commercial use would need a
  licence from DuckDuckGo (see their README) or a different tracker list.
- The CC licence does not cover DuckDuckGo's logos or marks; none are used here.

The tracker categories and "which domains of a big company count as tracking" rules in
`agent/trackers.py` are our own (hand-written), not part of the Tracker Radar data.

## Other files here (not committed)
- `sent_log.json`: log of every email send attempt (agent/mailer.py).
- `outbox/`: emails saved as .eml files when `SEND_MODE=outbox`.
