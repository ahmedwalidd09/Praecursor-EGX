# Consolidated-results disclosure study

## Extraction review

Checked three official November 12 exchange notices against the readable
homepage and the archived bilingual exchange payloads. The headline issuer,
scope and period agreed for IFAP consolidated July–September and RAYA
consolidated and standalone January–September. The archive carries an explicit
ISIN for all three notices. The old parser missed the spelled-out currency in
3/3 and extracted structured periods in 0/3. It also treated the RAYA
consolidated cross-post's unresolved `$33` and `$34` references as text.
That archive had no repeated revisions of these three entries. The collector
preserves content hashes and original first-seen times on repeat collection.
[Official exchange homepage](https://beta.egx.com.eg/en)

The three summaries supplied numeric profit figures with bilingual excerpts.
Units were unstated in the summaries, and the archived payload provided no
attachment URLs for these entries. Full statements were unavailable for
independent verification from the public detail route checked. The system
retains the amounts as stated, with unknown units and no computed growth,
comparative interpretation, or surprise signal. Ambiguous ticker, ISIN, and
conflicting bilingual field evidence are withheld. Different reporting scopes
remain distinct in the archive. [IFAP disclosure link](https://beta.egx.com.eg/en/media-center?tab=disclosure&newsCode=297600&openNewsDetails=1)

## Prospective protocol v1

Hypothesis: stocks with a recently published consolidated-results notice may
have a different next-session net scenario return from a technically similar
stock in the same original scan. Exposure uses a reported consolidated period
and an unambiguous ticker and ISIN. It never uses the direction or magnitude of
an earnings change. A notice must be published in the prior 24 hours and its
selected revision must actually have been known strictly before scan creation.
Cross-posts count at most once per symbol per scan. The first scan freezes the
match before 09:00 Cairo, recording the exact event revision and source.

Both securities need observed EGP quote currency at scan time and the existing
published-universe feature, price, turnover and quality gates. Select the first
matchable notice by publication time and a same-session control within 10
opportunity-score points and 0.5–2× turnover. Take the closest score match, with
symbol as tie-breaker. Controls lack an observed recent financial-results
notice in this feed. Each symbol can appear once in either role, and each
exposed ISIN and target session can appear once. Controls have no verified
universal issuer identifier, so issuer aliases remain a possible limitation.

A successful homepage snapshot at most six hours old supports partial coverage
only. Missing or stale feed checks are recorded separately from a fresh partial
snapshot with no match. Headlines and unmatched notices never count as returns.
The report uses both original horizon-aligned version-3 next-day outcomes at
25 bps, with a 50 bps additional stress per filled slot. Unfilled is cash,
ambiguity uses the existing stop-first scenario, and missing evidence leaves
the pair unresolved. Report counts and descriptive paired excess, with
five-session block-bootstrap uncertainty after 60 resolved distinct pairs.
The feed is selective and controls may have missed announcements. Estimates
are exploratory associations. No historical pairs are backfilled and the study
does not change live rankings, targets, labels or model promotion.
