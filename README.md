# CareerFit 💼

## סוכן חכם למציאת עבודה והכוונת קריירה

---

## סקירת הפרויקט

CareerFit הוא סוכן AI אינטראקטיבי לחיפוש עבודה מותאם אישית — עם תמיכה בישראל, ארה״ב וחיפוש גלובלי.
הסוכן מנהל שיחה חופשית בעברית ואנגלית, מבין את הפרופיל האישי של המשתמש ומציע משרות מהדאטה.

---

## מה הסוכן עושה?

- **שיחה חופשית** — מבין עברית, אנגלית ועברית-אנגלית מעורבת.
- **בונה פרופיל אישי** — שואל שאלות ממוקדות אחת בכל פעם.
- **חיפוש משרות חכם** — TF-IDF + ציון התאמה רב-ממדי.
- **הרחבת מיקום אוטומטית** — אם אין מספיק תוצאות באזור הראשי.
- **ניתוח פערי כישורים** — מה כדאי ללמוד.
- **דשבורד אנליטי** — מגמות, אשכולות, חריגות.

---

## דאטה

מקור: LinkedIn Job Postings (Kaggle).
- **postings.csv** — 3.3 מיליון משרות (הטבלה הראשית).
- **job_skills, salaries, job_industries, benefits** — מחוברים לפי `job_id`.
- **companies, company_industries, company_specialities** — מחוברים לפי `company_id`.

---

## הרצה מקומית

ראו את [run_project.md](run_project.md) לפקודות מלאות.

**קצר:**
```powershell
# Backend
python -m pip install -r backend\requirements.txt
python backend\data_pipeline.py     # עיבוד נתונים (~10 דקות)
uvicorn backend.main:app --reload   # http://localhost:8000

# Frontend (חלון נפרד)
cd frontend && npm install && npm run dev  # http://localhost:5173
```

---

## העלאה ל-GitHub

```powershell
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USER/careerfit-israel.git
git push -u origin main
```

> `data/archive.zip` לא מועלה — מוגדר ב-`.gitignore`.

---

## פריסה ל-Render

ראו [deployment_guide.md](deployment_guide.md) למדריך מלא.

- **Backend:** Render Web Service | root=`backend`
- **Frontend:** Render Static Site | root=`frontend`

---

## Backend API Endpoints

| Method | Path | תיאור |
|--------|------|--------|
| GET | `/health` | בדיקת תקינות ומצב DB |
| POST | `/chat` | שיחה עם הסוכן |
| POST | `/jobs/search` | חיפוש משרות ישיר |
| POST | `/data/process` | הפעלת pipeline ברקע |
| POST | `/data/cluster` | הפעלת clustering ברקע |
| GET | `/analytics/summary` | סיכום כללי |
| GET | `/analytics/trends` | מגמות ותרשימים |
| GET | `/analytics/anomalies` | חריגות |
| GET | `/analytics/clusters` | אשכולות |

---

## אלגוריתם ההתאמה

ציון התאמה 0–100 המורכב מ:

| קריטריון | משקל |
|----------|-------|
| התאמת כישורים | 30% |
| התאמת קטגוריה/עניין | 20% |
| דמיון TF-IDF | 20% |
| רמת ניסיון | 10% |
| מיקום | 10% |
| שכר | 5% |
| סביבת עבודה | 5% |

---

## NLP

- זיהוי שפה (עברית / אנגלית / מעורב).
- חילוץ השכלה, ניסיון, כישורים, תחומי עניין, שכר, מיקום, אילוצים.
- עדכון פרופיל אינקרמנטלי — רק שדות שהוזכרו מתעדכנים.
- ללא API חיצוני — Regex + Keyword Matching.

---

## Clustering

- TF-IDF על `combined_text_for_matching`.
- TruncatedSVD (50 רכיבים).
- KMeans (10 אשכולות).
- כל אשכול מקבל: כיוון קריירה, מילות מפתח, אזורים, קטגוריות.

---

## איתור אנומליות

- שכר גבוה/נמוך חריג.
- תיאורים חסרים/קצרים.
- חברה לא ידועה.
- ציון איכות נמוך.
- קטגוריות נדירות.

---

## מגבלות

1. נתוני LinkedIn אמריקאיים — המיפוי לישראל מבוסס על שמות מקומות.
2. SQLite לא מתמיד ב-Render — מתאים לסביבת פיתוח/דמו.
3. TF-IDF נבנה על מדגם (100K משרות) מטעמי זיכרון.
4. שפה עברית בנתונים מינימלית — הנתונים באנגלית.

---

## שיפורים עתידיים

- מודל שפה (HeBERT / Sentence-Transformers) לדמיון סמנטי.
- PostgreSQL לפרסום יציב.
- חיבור ל-LinkedIn API לנתונים ישראליים.
- פידבק לומד (Reinforcement Learning from Human Feedback).
- ממשק מובייל.
