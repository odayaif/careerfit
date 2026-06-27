# Location Coverage Report — CareerFit Dataset

**Generated:** June 2026  
**Dataset:** `backend/careerfit.db` — table `jobs_clean`  
**Total jobs:** 123,849

---

## Summary

This is a **US-centric LinkedIn dataset**. Zero jobs have an Israeli city in `location_clean`.
The matching engine now uses raw `location_clean` as the sole ground truth for location classification.

---

## Total Counts

| Metric | Count | % |
|--------|------:|--:|
| Total jobs | 123,849 | 100% |
| is_remote = 1 | 15,246 | 12.3% |
| is_remote = 0 | 108,603 | 87.7% |

---

## `location_area` Field Distribution

This field was set by the data pipeline keyword-matching English location text to Hebrew area names.
**The Israeli area values are corrupted** — they map to US "South/North/Center" locations, not Israel.

| location_area | Count | Notes |
|---------------|------:|-------|
| אחר (Other) | 107,077 | Majority — US/global non-remote |
| מרחוק (Remote) | 15,246 | Reliable — matches `is_remote=1` |
| **הצפון (North)** | **744** | **CORRUPTED — North US locations (e.g., "North Carolina", "Northampton, MA")** |
| **הדרום (South)** | **639** | **CORRUPTED — South US locations (e.g., "South San Francisco, CA", "Southlake, TX")** |
| **המרכז (Center)** | **135** | **CORRUPTED — Central US locations (e.g., "Central Texas")** |
| **השפלה** | **8** | **Likely corrupted — US locations** |

**Root cause:** The data pipeline matched English keywords ("South", "North", "Center") to Hebrew area names
(הדרום, הצפון, המרכז). These are NOT Israeli geographic areas in this dataset.

**Fix applied:** `classify_job_location()` no longer uses `location_area in ISRAEL_AREAS`.
Only raw `location_clean` text is used for Israeli classification.

---

## Israeli Location Coverage

| Signal | Count |
|--------|------:|
| Israeli city in `location_clean` | **0** |
| "Israel" in `location_clean` (any) | **0** |
| `location_area` = Hebrew Israeli area (corrupted) | 1,526 |

**Conclusion:** This dataset contains no jobs physically located in Israel.
It was scraped from the US LinkedIn market.

---

## New Classification Buckets (after fix)

| `job_country` value | Count | % | Description |
|---------------------|------:|--:|-------------|
| `Israel` | 0 | 0.0% | Confirmed Israeli location in raw data |
| `Israel_possible_remote` | 16 | 0.0% | Remote from known Israeli company (CyberArk, SentinelOne, NICE, etc.) |
| `global_or_foreign` | 19 | 0.0% | Remote, company definitively non-Israeli |
| `unknown_remote` | 15,211 | 12.3% | Remote, company Israel presence unknown |
| `United States` | 84,609 | 68.3% | US keyword in `location_clean`, non-remote |
| `Other` | 23,994 | 19.4% | Non-remote, non-US, unclassified |

---

## Israel_possible_remote — Jobs Available for Israel Search

These 16 jobs (from known Israeli companies, remote) are the **only Israel-relevant results** in the dataset:

| Company | Remote Jobs |
|---------|------------:|
| SentinelOne | 5 |
| NICE Systems | 4 |
| CyberArk | 3 |
| AU10TIX | 1 |
| monday.com | 1 |
| Telco Systems | 1 |
| Shoukhon Ltd | 1 |

---

## Known Israeli Companies Detected in Dataset

| Company | Total Jobs | Remote Jobs | Classification |
|---------|-----------:|-----------:|----------------|
| SentinelOne | 6 | 5 | Israel_possible_remote |
| NICE Systems | 4 | 4 | Israel_possible_remote |
| CyberArk | 3 | 3 | Israel_possible_remote |
| monday.com | 4 | 1 | Israel_possible_remote (1), United States (3) |
| Varonis | 8 | 1 | United States (7), Israel_possible_remote (1) — but Varonis remote has US location |
| Check Point | 3 | 0 | United States |
| Wix | 2 | 2 | United States (Wix is matched) |
| Amdocs | 3 | 0 | United States |
| Elbit Systems | 5 | 0 | United States |
| Fiverr | 1 | 0 | United States |
| AU10TIX | 1 | 1 | Israel_possible_remote |
| Telco Systems | 1 | 1 | Israel_possible_remote |
| Shoukhon Ltd | 1 | 1 | Israel_possible_remote |

---

## Frontend Display Labels (post-fix)

| `job_country` | Label shown to user |
|---------------|---------------------|
| `Israel` | 🇮🇱 {city} |
| `Israel_possible_remote` | 🌐 ייתכן רלוונטי לישראל |
| `United States` | 🇺🇸 {city} |
| `unknown_remote` | 🌐 מיקום לא ודאי |
| `global_or_foreign` | 🌐 מרחוק — לא ישראל |
| `Other` | 📍 {city} |

---

## Implications for Israel Search Mode

When a user selects **Israel** as their country preference:

1. `_fetch_candidates()` fetches only `is_remote = 1` jobs (15,246 candidates)
   - Avoids fetching the 1,526 corrupted "Israeli area" US jobs
2. After scoring, result assembly shows:
   - `Israel` bucket first (0 jobs in current dataset)
   - `Israel_possible_remote` bucket next (max 2 shown)
   - `unknown_remote` as last resort (if < 3 results found)
3. Jobs labeled 🌐 **ייתכן רלוונטי לישראל** are from Israeli tech companies and may be workable from Israel

**No job from Romania, the US, or Germany will ever receive the 🇮🇱 label.**

---

## Recommendations

1. **Connect to an Israeli job board** (Drushim, AllJobs, LinkedIn Israel) for genuine Israeli location data.
2. **PostgreSQL** with proper geolocation fields would eliminate the pipeline corruption issue.
3. In the meantime, the current fix ensures the 🇮🇱 label is never shown incorrectly.
