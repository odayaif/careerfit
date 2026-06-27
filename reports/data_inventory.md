# דו"ח בדיקת נתונים — CareerFit

**תאריך:** 2026-06-22 15:35

**נתיב ZIP:** `C:\Users\HP\OneDrive - The Academic College of Tel-Aviv Jaffa - MTA\שולחן העבודה\אודיה\לימודים\שנה ג\סמסטר ב\סדנת חדשנות ליהי\careerfit-agent\data\archive.zip`
**גודל ZIP:** 158.8 MB

## תוכן הארכיון

**סך קבצים:** 11
**קבצי CSV:** 11

| שם קובץ | גודל (MB) |
|---------|-----------|
| `companies/companies.csv` | 22.12 |
| `companies/company_industries.csv` | 0.75 |
| `companies/company_specialities.csv` | 4.23 |
| `companies/employee_counts.csv` | 1.00 |
| `jobs/benefits.csv` | 1.84 |
| `jobs/job_industries.csv` | 2.39 |
| `jobs/job_skills.csv` | 3.34 |
| `jobs/salaries.csv` | 2.15 |
| `mappings/industries.csv` | 0.01 |
| `mappings/skills.csv` | 0.00 |
| `postings.csv` | 492.90 |

---

## פירוט קבצי CSV

### `companies/companies.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 141,026
- **עמודות:** 10
- **שמות עמודות:** company_id, name, description, company_size, state, country, city, zip_code, address, url

**שורות לדוגמה:**

```
   company_id                        name                                                                      description  company_size  state country              city zip_code                                address                                                          url
0        1009                         IBM  At IBM, we do more than work. We create. We create as technologists, develop...             7     NY      US  Armonk, New York    10504  International Business Machines Corp.                         https://www.linkedin.com/company/ibm
1        1016               GE HealthCare  Every day millions of people feel the impact of our intelligent devices, adv...             7      0      US           Chicago        0                                      -                https://www.linkedin.com/company/gehealthcare
2        1025  Hewlett Packard Enterprise  Official LinkedIn of Hewlett Packard Enterprise, the global edge-to-cloud co...             7  Texas      US           Houston    77389            1701 E Mossy Oaks Rd Spring  https://www.linkedin.com/company/hewlett-packard-enterprise
```

### `companies/company_industries.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 24,375
- **עמודות:** 2
- **שמות עמודות:** company_id, industry

**שורות לדוגמה:**

```
   company_id                        industry
0      391906  Book and Periodical Publishing
1    22292832                    Construction
2       20300                         Banking
```

### `companies/company_specialities.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 169,387
- **עמודות:** 2
- **שמות עמודות:** company_id, speciality

**שורות לדוגמה:**

```
   company_id              speciality
0    22292832      window replacement
1    22292832  patio door replacement
2       20300      Commercial Banking
```

### `companies/employee_counts.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 35,787
- **עמודות:** 4
- **שמות עמודות:** company_id, employee_count, follower_count, time_recorded

**שורות לדוגמה:**

```
   company_id  employee_count  follower_count  time_recorded
0      391906             186           32508     1712346173
1    22292832             311            4471     1712346173
2       20300            1053            6554     1712346173
```

### `jobs/benefits.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 67,943
- **עמודות:** 3
- **שמות עמודות:** job_id, inferred, type

**שורות לדוגמה:**

```
       job_id  inferred               type
0  3887473071         0  Medical insurance
1  3887473071         0   Vision insurance
2  3887473071         0   Dental insurance
```

### `jobs/job_industries.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 164,808
- **עמודות:** 2
- **שמות עמודות:** job_id, industry_id

**שורות לדוגמה:**

```
       job_id  industry_id
0  3884428798           82
1  3887473071           48
2  3887465684           41
```

### `jobs/job_skills.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 213,768
- **עמודות:** 2
- **שמות עמודות:** job_id, skill_abr

**שורות לדוגמה:**

```
       job_id skill_abr
0  3884428798      MRKT
1  3884428798        PR
2  3884428798       WRT
```

### `jobs/salaries.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 40,785
- **עמודות:** 8
- **שמות עמודות:** salary_id, job_id, max_salary, med_salary, min_salary, pay_period, currency, compensation_type
- **ערכים חסרים (בדגימה):**
  - `med_salary`: 89.5%
  - `max_salary`: 10.5%
  - `min_salary`: 10.5%

**שורות לדוגמה:**

```
   salary_id      job_id  max_salary  med_salary  min_salary pay_period currency compensation_type
0          1  3884428798         NaN        20.0         NaN     HOURLY      USD       BASE_SALARY
1          2  3887470552        25.0         NaN        23.0     HOURLY      USD       BASE_SALARY
2          3  3884431523    120000.0         NaN    100000.0     YEARLY      USD       BASE_SALARY
```

### `mappings/industries.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 422
- **עמודות:** 2
- **שמות עמודות:** industry_id, industry_name
- **ערכים חסרים (בדגימה):**
  - `industry_name`: 1.5%

**שורות לדוגמה:**

```
   industry_id                    industry_name
0            1  Defense and Space Manufacturing
1            3  Computer Hardware Manufacturing
2            4             Software Development
```

### `mappings/skills.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 35
- **עמודות:** 2
- **שמות עמודות:** skill_abr, skill_name

**שורות לדוגמה:**

```
  skill_abr    skill_name
0       ART  Art/Creative
1      DSGN        Design
2      ADVR   Advertising
```

### `postings.csv`

- **קידוד:** utf-8
- **שורות (הערכה):** 3,383,601
- **עמודות:** 31
- **שמות עמודות:** job_id, company_name, title, description, max_salary, pay_period, location, company_id, views, med_salary, min_salary, formatted_work_type, applies, original_listed_time, remote_allowed, job_posting_url, application_url, application_type, expiry, closed_time, formatted_experience_level, skills_desc, listed_time, posting_domain, sponsored, work_type, currency, compensation_type, normalized_salary, zip_code, fips
- **ערכים חסרים (בדגימה):**
  - `closed_time`: 99.0%
  - `skills_desc`: 95.0%
  - `posting_domain`: 94.5%
  - `med_salary`: 94.0%
  - `formatted_experience_level`: 93.0%
  - `remote_allowed`: 83.5%
  - `application_url`: 81.5%
  - `applies`: 71.5%
  - `max_salary`: 62.5%
  - `min_salary`: 62.5%

**שורות לדוגמה:**

```
     job_id            company_name                              title                                                                      description  max_salary pay_period          location  company_id  views  med_salary  min_salary formatted_work_type  applies  original_listed_time  remote_allowed                                                      job_posting_url application_url    application_type        expiry  closed_time formatted_experience_level                                                                      skills_desc   listed_time posting_domain  sponsored  work_type currency compensation_type  normalized_salary  zip_code     fips
0    921716   Corcoran Sawyer Smith              Marketing Coordinator  Job descriptionA leading real estate firm in New Jersey is seeking an admini...        20.0     HOURLY     Princeton, NJ   2774458.0   20.0         NaN        17.0           Full-time      2.0          1.713398e+12             NaN    https://www.linkedin.com/jobs/view/921716/?trk=jobs_biz_prem_srch             NaN  ComplexOnsiteApply  1.715990e+12          NaN                        NaN  Requirements: \n\nWe are seeking a College or Graduate Student (can also be ...  1.713398e+12            NaN          0  FULL_TIME      USD       BASE_SALARY            38480.0    8540.0  34021.0
1   1829192                     NaN  Mental Health Therapist/Counselor  At Aspen Therapy and Wellness , we are committed to serving clients with bes...        50.0     HOURLY  Fort Collins, CO         NaN    1.0         NaN        30.0           Full-time      NaN          1.712858e+12             NaN   https://www.linkedin.com/jobs/view/1829192/?trk=jobs_biz_prem_srch             NaN  ComplexOnsiteApply  1.715450e+12          NaN                        NaN                                                                              NaN  1.712858e+12            NaN          0  FULL_TIME      USD       BASE_SALARY            83200.0   80521.0   8069.0
2  10998357  The National Exemplar         Assitant Restaurant Manager  The National Exemplar is accepting applications for an Assistant Restaurant ...     65000.0     YEARLY    Cincinnati, OH  64896719.0    8.0         NaN     45000.0           Full-time      NaN          1.713278e+12             NaN  https://www.linkedin.com/jobs/view/10998357/?trk=jobs_biz_prem_srch             NaN  ComplexOnsiteApply  1.715870e+12          NaN                        NaN  We are currently accepting resumes for FOH - Asisstant Restaurant Management...  1.713278e+12            NaN          0  FULL_TIME      USD       BASE_SALARY            55000.0   45202.0  39061.0
```
