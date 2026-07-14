# Design Decisions

Open items from the product design plan, locked for v1.

## Penalty shootouts
**Decision:** coin flip after knockout draw.  
**Why:** national-team shootout samples are tiny; modeling “penalty skill” creates false precision. Documented as a known weakness in the validation memo.

## Confederation adjustment
**Decision:** available as a toggle; **default off**.  
**Why:** inter-confederation friendly/qualifier mixes are biased; prior effects are easy to overfit. Sensitivity runs can turn it on.

## Re-simulation frequency
**Decision:** batch re-run after each completed real tournament match (scheduler); serve cached aggregates from Postgres.  
**Why:** mirrors overnight/batch risk recalculation. Interactive API demos may run small-N sims only.

## Host advantage
**Decision:** off for fully neutral tournaments unless `is_neutral=False` for the host’s matches.  
**Why:** host effects exist but are edition-specific; keep explicit rather than silent.

## Extra time
**Decision:** not modeled as a separate Poisson layer in v1 — draw in regulation → penalties coin flip.  
**Why:** ET goal rates differ; defer until knock-out calibration dataset is assembled.
