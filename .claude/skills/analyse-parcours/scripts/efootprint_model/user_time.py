#!/usr/bin/env python3
"""
User time per step: Nielsen 2008, recalibrated on a site measurement.

ZERO e-footprint import here either: this module only computes, it returns
`Traced` (cf. spec.py), never an e-footprint object.

THE FORMULA, CHECKED AT THE SOURCE (05 and 07/08/2026)
------------------------------------------------------
Nielsen, "How Little Do Users Read?", Nielsen Norman Group, May 5, 2008:
    "a fixed time of about 25 seconds, plus an additional 4.4 seconds
    per 100 words"
Published validity domain: "30 and 1,250 words"; beyond that, the article
says "reading became quite erratic".
URL: https://www.nngroup.com/articles/how-little-do-users-read/

Underlying study, whose formula is a statistical fit: Weinreich, Obendorf,
Herder & Mayer, "Not Quite the Average: An Empirical Study of Web Use", ACM
Transactions on the Web 2(1), art. 5, February 2008. 25 instrumented people
in NORMAL use, 59,573 page views at start, 45,237 after filtering. WEAKNESS TO
WRITE IN THE REPORT: 2005 data, before the smartphone (iPhone 2007).

WHY THE RECALIBRATION COMPARES TWO AVERAGES, NEVER A POINT TO AN AVERAGE
------------------------------------------------------------------------
SimilarWeb returns only one aggregate per site (TimeOnSite / PagePerVisit,
all pages and all visits mixed), never a time per page. To find a coherent
Nielsen counterpart, we therefore also need an average of pages, not a single
page. Checked at the source on 07/08/2026 (p. 5:19 of Weinreich et al.):
"these results are based on nearly 60,000 first-page visits [...] the average
number of words per page [...] was 551 words" — the study itself computes the
reading time PER INDIVIDUAL PAGE VIEW, never per session nor per site, and
then derives averages from it. Comparing average(raw Nielsen of the
journey's pages) to the SimilarWeb average is therefore the only
methodologically defensible correspondence; comparing the single home page
(done on the first tested site, with a single step) is no longer defensible
as soon as a journey has several steps.

RESERVE TO REPEAT IN THE REPORT, whichever path is chosen:
- the recalibration factor is computed on A SINGLE site, not generic
  (cf. check_genericite.py: 0.41 is a forbidden value in this file);
- the captured journey is only a subset of the pages that SimilarWeb
  averages over the WHOLE site.

TWO CONFIDENCE DOWNGRADES, WRITTEN, NEVER SILENT
------------------------------------------------
1. Page outside the Nielsen validity domain (30-1250 words): the formula is
   applied anyway (better than no number), but the confidence drops and the
   reason is written in the `Traced`'s comment.
2. No SimilarWeb measurement available for recalibration (site ignored by
   SimilarWeb, intranet, Engagments absent): the RAW Nielsen time is used,
   confidence degraded, reason written (the raw value is structurally
   overestimated for a site with significant mobile usage, cf. C.6 of the
   plan).
"""

from .spec import assumed, estimated

_SOURCE_NAME = "Nielsen 2008 (nngroup.com), formula fitted on Weinreich et al. 2008 (ACM ToWeb)"  # genericity: ok - universal source of the method, not an audit case
_SOURCE_URL = "https://www.nngroup.com/articles/how-little-do-users-read/"  # genericity: ok - universal source of the method, not an audit case

NIELSEN_BASE_SECONDS = 25.0
NIELSEN_SECONDS_PER_100_WORDS = 4.4
NIELSEN_DOMAIN_MIN_WORDS = 30.0
NIELSEN_DOMAIN_MAX_WORDS = 1250.0


def nielsen_raw_seconds(word_count):
    """Raw reading time, Nielsen 2008 formula: 25 s + 4.4 s / 100 words.

    Pure function of `word_count`, without provenance: it is up to the
    callers (`step_user_time`) to wrap the result in a `Traced`, once they
    know whether the validity domain and the recalibration apply.
    """
    return NIELSEN_BASE_SECONDS + NIELSEN_SECONDS_PER_100_WORDS * (word_count / 100.0)


def is_within_nielsen_domain(word_count):
    """Does the word count fall inside the published domain (30-1250)?"""
    return NIELSEN_DOMAIN_MIN_WORDS <= word_count <= NIELSEN_DOMAIN_MAX_WORDS


def recalibration_factor(avg_time_on_page_s, nielsen_raw_seconds_by_step):
    """Recalibration factor: measured average time (SimilarWeb) / average of
    the raw Nielsens of the journey's pages that have a word count.

    avg_time_on_page_s        : TimeOnSite / PagePerVisit of the SimilarWeb
                                 Engagments block (average of the WHOLE site),
                                 or None if unavailable (cf.
                                 similarweb_api.py).
    nielsen_raw_seconds_by_step : raw Nielsens (nielsen_raw_seconds()) of the
                                 journey's steps that have a measured word
                                 count, including those outside the domain
                                 (30-1250): the validity domain concerns
                                 the CONFIDENCE to display per step, not
                                 the admissibility of a page in this
                                 reference average.

    Returns None if the recalibration is IMPOSSIBLE (no SimilarWeb
    measurement, or no journey page has a word count): an absence of
    measurement, not a zero factor that would crush all times to zero.
    """
    if avg_time_on_page_s is None:
        return None
    raws = [r for r in nielsen_raw_seconds_by_step if r is not None]
    if not raws:
        return None
    mean_raw = sum(raws) / len(raws)
    if mean_raw <= 0:
        return None
    return avg_time_on_page_s / mean_raw


def step_user_time(word_count, factor):
    """`Traced` of a step's user time, Nielsen formula + recalibration.

    word_count : measured word count of the page (cf. from_har.py), or None
                 if unavailable (Lot 3 fallback: HTML body not captured).
                 In that case the function returns None: it is up to the
                 caller to keep ITS OWN explicit fallback, rather than
                 guessing one here.
    factor      : factor from `recalibration_factor()`, or None if the
                 recalibration is unavailable for this site.

    Confidence "medium" (estimated) ONLY if BOTH conditions hold: page
    within the validity domain AND recalibration available. Otherwise "low"
    (assumed), with the reason written in the comment — never a degraded
    badge without explanation.
    """
    if word_count is None:
        return None

    raw = nielsen_raw_seconds(word_count)
    within_domain = is_within_nielsen_domain(word_count)
    recalibrated = factor is not None
    value = raw * factor if recalibrated else raw

    reasons = []
    if not within_domain:
        reasons.append(
            f"page outside the Nielsen validity domain (30 to 1250 words; "
            f"measured {word_count:.0f}): beyond that, the article documents a "
            "\"quite erratic\" reading, the formula is applied but less reliable."
        )
    if not recalibrated:
        reasons.append(
            "no SimilarWeb measurement (TimeOnSite/PagePerVisit) available "
            "for this site: RAW Nielsen time, not recalibrated, probably "
            "OVERESTIMATED (underlying study from 2005, before the smartphone)."
        )

    base = (
        f"Nielsen 2008: 25 s + 4.4 s/100 words ({word_count:.0f} words), "
        f"recalibrated by a factor {factor:.3f} measured on this site (average "
        "SimilarWeb TimeOnSite/PagePerVisit divided by the average of the "
        "journey pages' raw Nielsens)."
        if recalibrated else
        f"Nielsen 2008: 25 s + 4.4 s/100 words ({word_count:.0f} words), WITHOUT recalibration."
    )
    comment = " ".join([base] + reasons)

    factory = estimated if (within_domain and recalibrated) else assumed
    return factory(value, "s", _SOURCE_NAME, _SOURCE_URL, comment)
