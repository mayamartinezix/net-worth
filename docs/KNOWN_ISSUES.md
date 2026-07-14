"""Known gaps from the post-scaffold review (tracked openly for portfolio honesty).

Fixed in the final-four pass
----------------------------
- Frontend loading used `startTransition(async)` → pending cleared too early; now explicit loading + request id.
- Odds table omitted R16; now included.
- Odds team-name aliases (USA ↔ United States, etc.) applied on WC odds export.
- SQL schema missing `p_r32`; added.
- Final Four comparison endpoint + UI section for WC 2026 semis.

Still open (higher effort / documented intentionally)
----------------------------------------------------
1. **Official knockout seeding** — WC48 / Euros use a simplified qualifier order,
   not the FIFA/UEFA pairing tables. Path odds are approximate.
2. **Full H2H / fair-play tiebreakers** — standings use points → GD → GF only.
3. **Live conditioning for full-field odds** — full-field table still resimulates
   from kickoff; Final Four view *does* condition on the confirmed semis.
4. **Host advantage in tournament sims** — still forced neutral for now.
5. **Calibrated Poisson params / form features** — defaults remain for v1 demos.
6. **Cached `simulation_results` serve path** — demo API still runs small live N.
"""
