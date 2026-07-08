## Mission
NRT is a professional decision-support application that helps knowledge workers make effective use of short periods of available time. Rather than asking users to decide what to do next, NRT continuously curates and prioritizes professional activities based on their goals, interests, and current context.

## Initial target users (in order):
1. psychologists
1. ML/software engineers

## Day in the life

This section considers example users.

### Sarah

Sarah is a licensed psychologist. She has 20 minutes between clients. Rather than deciding whether to read email, browse social media, or catch up on professional news, she opens NRT. NRT recommends three activities:

- A 6-minute summary of a new state licensing requirement.
- A 12-minute podcast discussing recent changes to informed consent guidance.
- A previously saved article on a therapy technique aligned with one of her learning goals.

Sarah spends the next 15 minutes listening to the podcast, marks it complete, and returns to work confident she used her available time well.

### Alex

Alex is an MLE working in Big Tech, and he has 30 minutes before a design review. Instead of stopping to think for awhile about how to use that time, he opens NRT, which recommends:

- A blog post on a recently announced ML framework feature
- A conference talk relevant to his current project
- A GitHub issue discussing an upcoming breaking API change.

Alex reads the blog post before the design review and discovers a recently released feature relevant to the discussion.

## Core values:

- reduce cognitive overhead
- maintain professional awareness
- support incremental learning
- use time effectively

## Design Principles

- Reduce decisions, don't create them. The application should recommend a small number of high-quality next actions rather than presenting long lists.
- Professional growth happens incrementally. The product should assume most interactions last between 5 and 30 minutes.
- Prioritize action over information. Information is only valuable if it helps the user decide what to do next.
- Respect the user's attention. Avoid unnecessary notifications, clutter, and interruptions.
- Recommendations should be explainable. The user should understand why something was recommended.
- Trust is earned. Recommendations should be timely, relevant, and drawn from credible sources. Users should rarely feel that NRT wasted their time.

## Initial Scope

The first version focuses on:

- ingesting professional content
- managing professional goals
- recommending high-value activities
- tracking user interactions

## Long-Term Vision

Future versions may:

- incorporate richer personalization
- support long-term professional planning
- integrate calendars and task managers
- incorporate gamification techniques that encourage sustained engagement while avoiding manipulative behavior
- adapt recommendations based on observed user preferences and behavior

## Non-Goals

At least initially, NRT is not intended to:

- replace a general-purpose task manager
- replace a calendar
- become a social network
- maximize time spent in the application
- recommend content outside the user's professional goals

## Success

A successful interaction with NRT is one in which:

- the user spends little or no time deciding what to do;
- the recommended activity is completed;
- the user feels the time was well spent;
- the user returns to work more informed or more prepared than before.