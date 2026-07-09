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

A Goal represents something the user wants to accomplish
professionally.

Examples include:

- Learn Bayesian statistics.
- Stay current on California psychology regulations.
- Prepare for AWS certification.

Goals are long-lived.

Goals influence recommendation ranking.

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

A Content Item may satisfy one or more Goals.

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

A Professional Profile represents a package of skills and interests. Each User
may ultimately have more than one Professional Profile. 

Examples:

- Machine Learning Engineer
- Psychologist
- Adjunct Professor

Professional Profiles are independent of individual users.

## Relationships
User
 ├── owns Goals
 ├── owns Professional Profiles
 ├── subscribes to Content Sources
 ├── receives Recommendations
 └── produces Interactions

Content Source
 └── produces Content Items

Content Item
 ├── belongs to Content Source
 ├── relates to Topics
 └── helps satisfy Goals

Recommendation
 ├── presented to User
 └── recommends Content Item

Interaction
 ├── belongs to User
 └── references Recommendation

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