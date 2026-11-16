# Domain Model

## Overview

The NRT domain consists of users pursuing professional goals through recommended activities. Activities are generated from professional content and are prioritized according to user goals, preferences, available time, and context.

## Core Entities

### User

A User is an individual who uses NRT to receive professional
recommendations.

A User owns:

- Goals
- Content Sources
- Recommendation History
- Preferences

A User has exactly one professional profile, although future
versions may support multiple professional identities.

A User is the top-level owner of almost all user-generated data.

### Goal

A Goal represents a long-lived professional objective that guides the
user's learning and work.

Goals define what success looks like for the user. They are independent
of any particular Content Source, Content Item, or Recommendation.

Examples include:

- Learn Bayesian statistics.
- Learn Bayesian statistics by March 2027.
- Stay current on California psychology regulations.
- Prepare for AWS certification.

A Goal has:

- A title.
- An optional description.
- A lifecycle status.
- An optional target date.
- A creation timestamp.
- A modification timestamp.
- An optional completion timestamp.

A Goal belongs to exactly one User. A User may have multiple Goals.

Goals have the following lifecycle states:

- Active
- Paused
- Completed
- Archived

A Goal is completed when the User declares that they have accomplished it.
The system does not automatically mark a Goal as completed when its target
date passes.

A target date represents the date by which the User intends to accomplish
the Goal. It is optional and represents a calendar date rather than a
specific time.

Goals may be associated with Topics. Topic associations provide a
user-independent semantic bridge between Goals and Content, allowing NRT
to discover potentially relevant Content Sources and Content Items without
requiring expensive model inference for every recommendation.

Goals may be hierarchical in the future. Hierarchical Goals are not part
of the initial implementation.

### Content Source

A Content Source represents a user-configured origin from which NRT may
discover Content Items.

Examples:

- RSS feed
- Podcast
- Professional organization
- Government website
- Journal

For the initial implementation, RSS is the only supported source type.
`ContentSource.source_type` describes how/where content is obtained;
`ContentItem.content_type` describes what kind of content it is. They are
independent: a future RSS source may produce `podcast_episode` items without a
new source type.

Content Source lifecycle status (`active`, `paused`, or `archived`) controls
whether NRT dispatches the source. RSS fetch health is separate operational
metadata from the most recent attempt: a source can be paused and still show
that its most recent fetch was healthy. Health records the latest attempt, the
latest successful fetch, and a restrained diagnostic for an invalid feed or
fetch failure. A source with no attempt has never been checked.

### Content Item

A Content Item is a piece of content discovered from a Content Source and
potentially eligible to produce a candidate Action. It belongs to the User who
owns that Content Source.

Examples:

- Article
- Podcast episode
- Conference talk
- Regulation summary
- GitHub release

Every Content Item originates from exactly one Content Source. Its source-specific
external identity prevents duplicate discovery from that source; the same URL may
be discovered from different Content Sources. A missing item from a later feed
poll does not delete the previously discovered Content Item.

A Content Item always records when NRT discovered it. Its publication time may be
absent when the source does not provide a reliable value.

Content Item is the generic durable content object. Its common fields are `id`,
`user_id`, `content_source_id`, `content_type`, `external_id`, `title`, `url`,
`summary`, `published_at`, `discovered_at`, `created_at`, and `updated_at`.
`content_type` is required and constrained to `article`, `podcast_episode`,
`video`, `research_article`, or `book`. Existing items are backfilled as
`article`; ordinary RSS ingestion continues to produce articles without type
inference. Other values establish a contract, not new ingestion capabilities.

Optional `duration_minutes` is a positive integer recording known/source-provided
expected consumption time. Unknown duration is `null`, including ordinary RSS
articles. It is never populated from a summary heuristic. Candidate Action
`estimated_duration_minutes` is resolved at runtime: use known duration when
present, otherwise the existing deterministic summary-based reading estimate
(225 words/minute, minimum five minutes). This fallback also applies to future
types until a later slice explicitly changes it. Known duration is not clamped
to the five-minute minimum or the available-time window.

Topic and Goal relationships and type-specific metadata are future concepts and
are not part of the current persisted Content Item model.

### Recommendation

A Recommendation is a suggestion presented to a User.

Recommendations are transient.

A Recommendation always refers to one actionable item.

Examples:

- Read an article.
- Listen to a podcast.
- Continue a learning path.

Recommendations are generated from:

- User Goals
- User Preferences
- Available Content
- Estimated effort
- Current context

### Interaction

An Interaction records how a User responded to a Recommendation.

Examples:

- opened
- dismissed
- completed
- saved for later

Interactions allow NRT to improve future recommendations.

### Topic

A Topic represents a professional subject.

Examples:

- Cognitive Behavioral Therapy
- Information Theory
- Reinforcement Learning

Topics organize Content Items.

Topics are independent of individual users.

### Professional Profile

A Professional Profile represents a professional role or identity
through which a user consumes content and receives recommendations. Each User
may ultimately have more than one Professional Profile. 

Examples:

- Machine Learning Engineer
- Psychologist
- Adjunct Professor

Professional Profiles are independent of individual users.

### Recommendation Event

A Recommendation Event records a single recommendation decision made for a User.

Each Recommendation Event represents one execution of the recommendation engine.

A Recommendation Event records:

- the Action that was recommended
- when it was recommended
- why it was recommended
- the context in which it was recommended
- how the user responded

Recommendation Events are immutable historical records of what NRT recommended.

Recommendation Events are used to:

- explain recommendations
- improve future recommendations
- avoid excessive repetition
- evaluate recommendation quality

A Recommendation Event records a durable `consume_content_item` decision,
its available-time context, resolved estimated duration,
deterministic score, explanation, and optional future outcome. The referenced
Candidate Action itself is not persisted. Historical `read_content_item` events
remain valid and unchanged; new decisions use `consume_content_item`. Event
`action_type` remains text, without a new constraint or history rewrite.

### Candidate Action

A Candidate Action is an ephemeral internal representation of one actionable
option considered during a recommendation request. Content Items produce
`consume_content_item` Candidate Actions: perform the primary consumption action
associated with the item. Each candidate preserves `content_type` and resolves
`estimated_duration_minutes` from known duration or the existing heuristic.
Candidate Actions are not database entities and are discarded after ranking.

Content Item = generic durable content; Candidate Action = ephemeral thing the
User can do; Recommendation Event = durable recommendation decision. New action
labels, ingestion, and type-specific scoring are outside this contract slice.

### Content Item User State

Content Item User State is the mutable current disposition of one Content Item
for one User. It is `active`, `completed`, or `archived`. Snooze is temporal
eligibility rather than a permanent status: an active item with a future
`snoozed_until` is temporarily ineligible. `completed` is intentionally generic
and applies to any activity type, not only reading.

### User Action Event

A User Action Event is an immutable record of a user's disposition action:
`snoozed`, `completed`, or `archived`. It may link to the Recommendation Event
that prompted it. It does not replace Recommendation Event history or mutable
Content Item User State.

### Action

An Action represents a professional activity that a user could perform.

Actions are the unit of work considered by the recommendation engine.

Examples include:

- Read an article.
- Listen to a podcast episode.
- Continue a learning path.
- Review previously saved notes.
- Work on an active project.
- Complete a certification module.

Actions may originate from Content Items, user Goals, application logic, or future integrations.

Actions are independent of any individual recommendation.

The same Action may be recommended many times over its lifetime.

### Recommendation Outcome

A Recommendation Outcome records the user's response to a Recommendation Event.

Examples include:

- Opened
- Completed
- Dismissed
- Saved for later
- Expired

A Recommendation Outcome belongs to exactly one Recommendation Event.

## Relationships
User
 ├── owns Goals
 ├── owns Professional Profiles
 ├── subscribes to Content Sources
 ├── owns Recommendation Events
 └── produces Recommmendation Outcomes

Action
 ├── may reference one or more Content Items
 ├── may support one or more Goals
 └── may be recommended many times

Recommendation Event
 ├── belongs to one User
 ├── recommends one Action
 └── records one Recommendation Outcome

Content Source
 └── publishes Content Items

Content Item
 ├── belongs to Content Source
 └── relates to Topics


## Terminology

| Term           | Meaning                                     |
| -------------- | ------------------------------------------- |
| Goal           | Desired professional outcome                |
| Topic          | Subject area independent of users           |
| Content Source | Origin of professional information          |
| Content Item   | Individual piece of information             |
| Recommendation | Suggested next action presented to the user |
| Interaction    | User response to a recommendation           |

Goal is not synonymous with Topic.

A Goal belongs to a user.

A Topic exists independently.

Those distinctions save a surprising amount


## Future Concepts

The following concepts are intentionally omitted
from the current model.

- Organizations
- Teams
- Mentors
- Shared learning plans
- Certifications
- Calendar events
- Tasks
