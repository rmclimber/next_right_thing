# Podcast Support — Initial Slice

## Objective

Register a podcast RSS feed, ingest episodes, and discover them through existing
Content Item and Recommendation workflows. This extends ADR-0007's deployed
contract and the existing ingestion pipeline; it adds no database migration,
API fields, dependencies, source types, or infrastructure.

## Behavior and decisions

- Register a podcast's public HTTP(S) RSS feed with the existing Content Sources
  form/API. It remains an active `rss` Content Source. Registration does not
  fetch synchronously; existing dispatch polls active feeds every 120 minutes.
- Classify each entry independently as `podcast_episode` when it has an
  HTTP(S) enclosure whose MIME type is `audio/*`. Use the first usable audio
  enclosure, ignoring video, invalid URLs, and missing/non-audio MIME types.
  Enclosure URLs require a hostname; malformed or out-of-range ports are skipped
  so a later valid enclosure can still be used.
  Ordinary entries retain the existing article payload and Writer defaults.
- Store the episode title, description in `summary`, publication time when
  reliable, and discovery time using the common Content Item fields. Description
  precedence is summary, iTunes summary, subtitle, then content body. Missing or
  malformed optional values are null. Missing required title or a usable item
  URL/identity skips that entry without blocking other entries.
- Store the audio enclosure in the existing `url` field. Both list and
  recommendation links use it for external listening; no new media URL field or
  Candidate Action field is necessary. The episode permalink is used only as an
  identity fallback, not persisted separately.
- Preserve source-specific identity: GUID/Atom ID, then entry link, then audio
  enclosure URL. Writer uniqueness remains `(content_source_id, external_id)`.
  Repeat polls/deliveries do not overwrite metadata or discovery time. Previously
  ingested articles are not reclassified on repeat discovery. No backfill is
  included; entries without stable GUIDs/permalinks can duplicate if their audio
  URL changes.
- Accept iTunes duration as integer seconds, `MM:SS`, or `HH:MM:SS`; subordinate
  components must be less than 60. Round positive seconds up to whole minutes.
  Missing, zero, negative, fractional, malformed, and out-of-PostgreSQL-range
  duration values are null. No consumption estimate is stored as known duration.
- Show a Podcast episode label in Content Items and Recommendation results,
  known duration or “Duration unknown” in the list, and “Listen externally”
  links that open a new tab. Article labels and actions retain their behavior.
- Recommendations continue using `consume_content_item`, known duration or the
  existing summary-based fallback, and the unchanged soft duration eligibility:
  exceeding the available-time window lowers duration fit but does not exclude
  the item. Complete, Snooze, Archive, history, and ownership rules are unchanged.

## Boundaries and rollout

Deploy the already-extended Writer and shared schema before enabling this Fetch
producer; older Writers reject the explicit type/duration fields. That shared
contract is already deployed for this work. Frontend presentation and Fetch can
then ship through the normal approved release process; no release is performed
as part of implementation.

Podcast parsing is encapsulated within RSS Fetch. No semantic scoring,
embeddings, or relevance infrastructure changes belong to this slice. The
parallel relevance track can consume the existing title/summary, type, and
duration fields without another contract change. Shared design/API documents
may require normal text conflict resolution when integrating the tracks.

No embedded player, playback-position tracking, subscriptions, download
management, podcast directory discovery, audio transcription, or enclosure
reachability probe is included. Missing/incorrect audio MIME declarations are
not guessed from filenames or iTunes metadata: a linked entry follows the
existing article path, otherwise it is skipped. Unknown-duration episodes keep
the shared reading-time fallback; a distinct listening estimate is deferred.
