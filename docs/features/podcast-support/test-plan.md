# Podcast Support Test Plan

## Automated behavior

- Given an authenticated user, when they add a podcast feed URL through the
  existing source form/API, then it is stored as an active RSS Content Source.
- Given a real RSS document with iTunes metadata and an audio enclosure, when
  RSS Fetch parses it, then title, summary, audio URL, publication time, type,
  and rounded known duration survive queue delivery, Writer persistence,
  Content Items listing, and Recommendation selection.
- Given missing GUID/permalink, description, date, or duration, when an entry has
  a title and valid audio enclosure, then it ingests with audio identity and
  nullable optional metadata. Malformed date/duration values do not fail the
  feed or suppress good sibling entries.
- Given multiple, non-audio, malformed, or absent enclosures, when normalizing,
  then the first valid HTTP(S) audio enclosure wins. Entries without one keep
  article behavior or are skipped if required article fields are absent.
  Missing hostnames and malformed/out-of-range ports must not override a later
  valid enclosure; valid explicit ports and IPv6 hosts remain supported.
- Given repeat polls, duplicate SQS deliveries, or changed metadata under the
  same identity, when Writer runs, then only one item exists per source/identity
  and its original metadata remains intact.
- Given known duration, when recommending, then it remains eligible even more
  than 25% beyond the available-time window. Given unknown duration, then the
  existing summary estimate is used. No scoring weights or eligibility rules
  change.
- Given episodes in list/recommendation responses, when rendering, then the UI
  labels them as podcast episodes and offers an external listening link.
  Opening that link does not mark the item complete. Complete, Snooze, and
  Archive use the existing actions and exclude items as before.
- Given another user, when listing, then they cannot see the episodes.
- Given ordinary RSS articles or historical `read_content_item` responses, when
  ingesting/rendering, then existing behavior is preserved.

Parser coverage: `backend/tests/test_podcast_parsing.py`.
Real PostgreSQL workflow: `backend/tests/test_podcast_pipeline.py`, using
`backend/tests/fixtures/podcast-feed.xml`. This test applies the deployed
migrations through `20261116_0008` inside an isolated schema, runs real source,
Writer, listing, Recommendation, and disposition repositories/APIs, and doubles
HTTP/SQS/Data API boundaries. It cleans up its schema. Set
`NRT_TEST_DATABASE_URL` to a disposable PostgreSQL database using a
`postgresql+psycopg://...` URL to enable it and the existing contract migration
integration test. Never point this at an application database.

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests
pnpm --filter @nrt/web test:run
pnpm --filter @nrt/web exec tsc --noEmit --incremental false
pnpm build
```

Frontend tests cover source registration, known/unknown duration, distinct
episode presentation, external listening, article/history compatibility, and
all disposition controls.

## Manual acceptance after an approved deployment

1. Sign in and add a public podcast RSS feed under Content Sources using its
   feed URL, not its website URL. Confirm active RSS status. Add an article RSS
   feed too, if none exists.
2. Allow the existing scheduled dispatch to run (up to 120 minutes). Refresh
   Content Sources and verify Healthy fetch status. For a quicker check, an
   operator can invoke Source Dispatch from their normal PowerShell using the
   command in `docs/content-item-ingestion.md`; Codex must not run AWS CLI.
3. Open Content Items. Verify episode title, description, source, date when
   provided, Podcast episode label, and known duration. A feed with absent or
   malformed duration should show Duration unknown. Verify ordinary articles
   still have Open article links and unchanged presentation.
4. Click Listen externally. Confirm a new tab opens the feed's audio URL and the
   episode remains active in NRT. Playback behavior is controlled by the feed
   host and browser.
5. Request recommendations for a short time window. When an episode is selected,
   verify its label, estimated duration, and listening link. An over-window
   duration does not make an otherwise eligible episode unavailable. For a
   deterministic check, use an account with only one eligible episode.
6. Test Complete, Snooze, and Archive on separate episodes. Confirm each advances
   to the next result and appears under its corresponding Content Items filter.
7. Let dispatch run again. Confirm identical episode identities do not increase
   item count or overwrite metadata. A newly published episode should appear.

Live feed reachability, real AWS queue delivery, and browser/host playback need
this acceptance pass; automated tests use local fixtures and PostgreSQL.
