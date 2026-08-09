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

A Goal represents a long-lived professional objective that guides
the user's learning and work.

Goals define what success looks like for the user. They are
independent of any particular content source or recommendation.

Examples include:

- Learn Bayesian statistics.
- Stay current on California psychology regulations.
- Prepare for AWS certification.

Goals have a lifecycle:
- Active
- Paused
- Completed
- Archived

Goals may be hierarchical in the future.

### Content Source

A Content Source is a provider of professional information.

Examples:

- RSS feed
- Podcast
- Professional organization
- Government website
- Journal

A Content Source periodically produces Content Items.

### Content Item

A Content Item is a single piece of professional information.

Examples:

- Article
- Podcast episode
- Conference talk
- Regulation summary
- GitHub release

Every Content Item originates from exactly one Content Source.

A Content Item may relate to one or more Topics.

A Content Item may be relevant to one or more Goals.

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

Recommendation Events are immutable historical records, except for the user's eventual outcome.

Recommendation Events are used to:

- explain recommendations
- improve future recommendations
- avoid excessive repetition
- evaluate recommendation quality

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