# הרצת CareerFit — Windows PowerShell

## דרישות מקדימות

- Python 3.10+ מותקן
- Node.js 18+ מותקן
- archive.zip ממוקם ב: `data\archive.zip`

---

## שלב 1 — כניסה לתיקיית הפרויקט

```powershell
cd "C:\Users\HP\OneDrive - The Academic College of Tel-Aviv Jaffa - MTA\שולחן העבודה\אודיה\לימודים\שנה ג\סמסטר ב\סדנת חדשנות ליהי\careerfit-agent"
```

---

## שלב 2 — התקנת תלויות Python

```powershell
python -m pip install -r backend\requirements.txt
```

> אם אין לך Python בדרך הנכונה:
> ```powershell
> py -m pip install -r backend\requirements.txt
> ```

---

## שלב 3 — בדיקת נתונים (אופציונלי)

```powershell
python backend\data_inspector.py
```

פלט: `reports\data_inventory.md`

---

## שלב 4 — עיבוד נתונים (חובה לפני חיפוש משרות)

```powershell
python backend\data_pipeline.py
```

> ⚠️ **זה לוקח זמן** — 3.3M שורות. צפוי: 5–20 דקות לפי מהירות המחשב.
> 
> אחרי הסיום נוצר: `backend\careerfit.db`

---

## שלב 5 — Clustering (מומלץ לאחר pipeline)

```powershell
python backend\clustering_engine.py
```

---

## שלב 6 — הרצת Backend

```powershell
uvicorn backend.main:app --reload
```

**ברירת מחדל:** http://localhost:8000

בדיקת בריאות: http://localhost:8000/health

תיעוד API: http://localhost:8000/docs

---

## שלב 7 — הרצת Frontend (חלון PowerShell נפרד)

```powershell
cd "C:\Users\HP\OneDrive - The Academic College of Tel-Aviv Jaffa - MTA\שולחן העבודה\אודיה\לימודים\שנה ג\סמסטר ב\סדנת חדשנות ליהי\careerfit-agent\frontend"
npm install
npm run dev
```

**Frontend:** http://localhost:5173

---

## הרצה מהירה (אחרי שהכל מותקן)

**חלון 1 — Backend:**
```powershell
cd "...careerfit-agent"
uvicorn backend.main:app --reload
```

**חלון 2 — Frontend:**
```powershell
cd "...careerfit-agent\frontend"
npm run dev
```

---

## בדיקת הצ'אט

1. פתחו http://localhost:5173
2. כתבו בצ'אט: `אני סטודנטית למערכות מידע, יודעת SQL ו-Excel`
3. ענו על השאלות שהסוכן שואל.
4. לחצו **חפש לי משרות** לראות תוצאות.

---

## פקודות שימושיות

```powershell
# ביטול הרצה
Ctrl+C

# בדיקת שגיאות backend בלוג
uvicorn backend.main:app --reload --log-level debug

# ניתוח אנומליות ידני
python backend\anomaly_engine.py
```

---

## נתיבי קבצים חשובים

| קובץ | תיאור |
|------|--------|
| `data\archive.zip` | קובץ הנתונים (לא מועלה ל-GitHub) |
| `backend\careerfit.db` | מסד הנתונים (נוצר אחרי pipeline) |
| `reports\` | כל הדו"חות האקדמיים |
| `backend\main.py` | API Server |
| `frontend\src\App.jsx` | React App |
