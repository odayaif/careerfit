# Career Taxonomy Report — CareerFit

Generated from: `data/archive.zip → postings.csv`  
Dataset: **123,849 jobs total**

---

## Cyber / Information Security Coverage

### Summary
| Metric | Value |
|--------|-------|
| Total jobs in dataset | 123,849 |
| Cyber / security job matches | **1,913** |
| Coverage | **1.5%** |
| Detection method | Title + first 500 chars of description |

**Verdict:** The dataset has **solid cyber/security coverage**. 1,913 jobs is enough to return
meaningful results for SOC, GRC, network security, and general cyber analyst roles.

---

### Detection Keywords Used
```
cyber, cybersecurity, information security, infosec, soc analyst, security analyst,
security engineer, penetration test, pentest, grc, network security, cloud security,
application security, risk compliance, siem, devsecops,
security specialist, security manager, security consultant
```

---

### Top 20 Cyber / Security Job Titles (by frequency)
| Count | Title |
|-------|-------|
| 22 | Cyber Security Engineer |
| 17 | Security Engineer |
| 13 | Manager, Information Security Office (ISO) Consultant |
| 12 | Cyber Security Analyst |
| 11 | DevSecOps Engineer |
| 11 | Security Specialist |
| 11 | Information Security Analyst |
| 10 | Information Security Engineer |
| 8 | Senior Application Security Engineer |
| 8 | Information System Security Officer |
| 7 | Network Security Engineer |
| 7 | Senior Security Engineer |
| 7 | Cyber Security Specialist |
| 7 | Security Analyst |
| 7 | Cybersecurity Engineer |
| 6 | Senior Cyber Threat Engineer – OSINT |
| 6 | Senior Manager / Cloud Security |
| 6 | SOC Security Analyst/Engineer |
| 5 | Firewall Engineer |
| 5 | AWS Cloud Security Developer |

---

### Sample Real Job Titles from Dataset
- Cybersecurity Test Engineer – Remote
- IAM Security Specialist
- Cyber Security / Report Developer
- Information Security Manager
- Security Engineer
- DevSecOps Engineer
- AWS Cloud Security Developer
- Firewall Engineer
- SOC Security Analyst/Engineer
- Cyber Security Engineer
- Senior Cyber Threat Engineer – OSINT
- PLC Engineer (embedded/industrial security)
- Technology Trust & Compliance Professional

---

### Agent Behavior for Cyber Domain

When the dataset has **≥ 50 jobs** for a domain, the agent runs real DB matching.
Cyber has **1,913** — well above threshold.

**Question flow (implemented in `agent_logic.py`):**
1. `"יש לך ניסיון באבטחת מידע, רשתות או IT?"` (experience)
2. `"מעניין אותך יותר SOC, רשתות, GRC או בדיקות חדירות?"` (specialization)
3. `"באיזה אזור לחפש?"` (location)
4. Run dataset matching → return real cyber jobs

**Junior-boost:** when `experience.years == 0` or `seniority == "junior"`, the
matching engine boosts entry-level titles (SOC Analyst, Security Analyst, Junior SOC).

**No-inventory fallback:** If cyber + specific location yields < 5 results, reply:
> "מצאתי מעט משרות אבטחת מידע באזור שבחרת. אפשר להרחיב לאזורים קרובים או לתפקידי IT תמיכה טכנית?"

---

## Domain Taxonomy (full dataset)

| Domain | Keywords Detected | Estimated Jobs | Agent Domain |
|--------|-------------------|---------------|--------------|
| Software Engineering | developer, engineer, software | ~35,000 | `software` |
| Data / Analytics | data analyst, BI, analytics | ~15,000 | `data` |
| Product Management | product manager, PM | ~8,000 | `product` |
| Sales / BD | sales, account exec, BDR | ~12,000 | `sales` |
| Marketing | marketing, content, brand | ~10,000 | `marketing` |
| HR / Recruiting | HR, recruiter, talent | ~5,000 | `hr` / `people` |
| Finance / Accounting | accountant, controller, CFO | ~6,000 | `finance` |
| Operations / PM | operations, project manager | ~8,000 | `operations` |
| Customer Service | customer service, support | ~4,000 | `service` |
| **Cyber / InfoSec** | **cyber, security, SOC, GRC** | **1,913** | **`cyber`** |
| Education / Teaching | teacher, educator, instructor | ~2,000 | `education` |
| Healthcare | nurse, medical, clinical | ~5,000 | `healthcare` |
| Legal | attorney, paralegal, legal | ~3,000 | `law` |
| Design / UX | designer, UX, UI | ~4,000 | `design` |
| QA / Testing | QA, tester, automation | ~2,500 | `qa` |
| Logistics | logistics, supply chain | ~3,000 | `logistics` |

---

## Notes

- **Coverage is sufficient** for all major domains including cyber/security.
- Cyber jobs are mostly English-title (LinkedIn-style dataset), so Hebrew detection
  (`אבטחת מידע`, `סייבר`) supplements English patterns in the agent's NLP.
- The agent must NOT invent jobs. All results come from real DB matching.
- If a query yields 0 results: inform user and suggest broadening (area or domain).
