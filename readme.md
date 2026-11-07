# Overveiw 
A browser agent that visits a site, clicks “Reject all” on the cookie banner, and watches what still gets sent anyway. It then reads the privacy policy, points out where the site broke its own promises, and drafts a complaint letter.

## Covers:
- Wordsmith (main): a long agent workflow with a legal angle.
- G-Research: it shows hidden tracking.
- Metaview: best overall, all projects are eligible.

Core Features 
1. Record everything: open the site and log every request, cookie and script it loads.
2. Reject cookies: the agent finds the cookie banner and clicks “Reject all”, including digging through “Manage preferences” if needed.
3. Browse after rejecting: the agent clicks around a few pages so trackers have a chance to fire.
4. Flag trackers: label which requests are trackers, using a known list like DuckDuckGo’s Tracker Radar or EasyPrivacy.
5. Read the policy: the agent finds the privacy policy and pulls out which companies it says it shares data with.
6. Compare: what they said against what actually happened, for example “Policy names 5 companies, we saw 18” or “Meta tracked you after you said no”.
7. Draft the letter: a complaint or data request (Subject Access Request) addressed to their data protection contact. It’s a draft only and never sent automatically.
8. Results page: a clear visual of what leaked, the broken promises, and the letter.
9. Check for crossite tracking. 

Additonal features 
- Fuck this site (send random data)
- Block ads 
- look for data collection in input boxes, eg typing a email into a   box w out submiting it 
- cnamw clokeing  

