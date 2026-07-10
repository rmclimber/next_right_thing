# Test Plan: Recommendations

## Objective

Verify that NRT can ingest professional content, generate recommendations,
present them to the user, and record user interactions.

## Happy Path

Given:
- A registered user
- At least one configured Content Source
- Newly ingested Content Items

When:
- The user opens the Recommendations page

Then:
- At least one Recommendation is displayed.
- The Recommendation references a valid Content Item.
- The Recommendation includes a rationale.
- The Recommendation includes an estimated duration.

---

## No Available Content

Given:
- A registered user
- No available Content Items

When:
- The user opens the Recommendations page

Then:
- The user is informed that no recommendations are currently available.
- The UI remains functional.

---

## Completing a Recommendation

Given:
- A displayed Recommendation

When:
- The user marks it as completed

Then:
- A corresponding Interaction is recorded.
- The Recommendation is no longer presented as active.

---

## Dismissing a Recommendation

Given:
- A displayed Recommendation

When:
- The user dismisses it

Then:
- A corresponding Interaction is recorded.
- The Recommendation is removed from the active recommendation list.

---

## Duplicate Content

Given:
- A Content Source republishes an existing Content Item

When:
- The ingestion worker runs

Then:
- No duplicate Content Item is created.
- Existing Recommendations remain valid.

---

## Recommendation Quality (v1)

Verify that Recommendations:

- Reference existing Content Items.
- Are generated only from subscribed Content Sources.
- Include a rationale.
- Can be completed or dismissed.

The recommendation algorithm itself is not evaluated beyond these guarantees.

---

## Out of scope

- Recommendation ranking quality
- Personalization
- Learning goal optimization
- Multi-device synchronization
- Performance under production-scale load