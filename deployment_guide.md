# מדריך פריסה — CareerFit

## 1. פתיחת GitHub Repository

1. כנסו ל-[github.com](https://github.com) ולחצו **New repository**.
2. שם: `careerfit-israel`
3. Public / Private — לפי בחירתכם.
4. **אל תוסיפו** README ו-.gitignore כי כבר קיימים בפרויקט.
5. לחצו **Create repository**.

---

## 2. העלאת הקוד ל-GitHub

פתחו PowerShell בתיקיית הפרויקט:

```powershell
cd "C:\Users\HP\OneDrive - The Academic College of Tel-Aviv Jaffa - MTA\שולחן העבודה\אודיה\לימודים\שנה ג\סמסטר ב\סדנת חדשנות ליהי\careerfit-agent"

git init
git add .
git commit -m "Initial CareerFit project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/careerfit-israel.git
git push -u origin main
```

> **החליפו** `YOUR_USERNAME` בשם המשתמש שלכם ב-GitHub.

---

## 3. למה לא מעלים archive.zip?

- הקובץ גדול מ-150MB — GitHub מגביל קבצים ל-100MB.
- הוא מכיל נתונים שמקורם ב-LinkedIn ואין לפרסמם.
- הקובץ מוגדר ב-`.gitignore` ולכן לא ייכלל ב-`git add .`.

---

## 4. הוספת Sample Data לדמו אונליין

לפריסה ציבורית עם נתונים:
1. הורידו sample קטן (1,000–5,000 שורות) מה-postings.csv.
2. שמרו אותו כ-`data/sample_postings.csv`.
3. עדכנו `data_pipeline.py` לקרוא מ-`sample_postings.csv` כשה-ZIP לא קיים.

לחלופין, הכינו DB מוכן (`careerfit.db`) ועלו אותו ישירות ל-Render עם Git-LFS.

---

## 5. עדכון קוד לאחר שינוי

```powershell
git add .
git commit -m "update: תיאור השינוי"
git push
```

---

## 6. פריסה ל-Render

### Backend (Web Service)

1. כנסו ל-[render.com](https://render.com) → **New Web Service**.
2. חברו ל-GitHub Repo שלכם.
3. הגדרות:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment Variables:
   - `FRONTEND_URL` = `https://careerfit-frontend.onrender.com`
   - `ENVIRONMENT` = `production`
5. לחצו **Deploy**.

### Frontend (Static Site)

1. **New Static Site** ב-Render.
2. חברו לאותו Repo.
3. הגדרות:
   - **Root Directory:** `frontend`
   - **Build Command:** `npm install && npm run build`
   - **Publish Directory:** `dist`
4. Environment Variables:
   - `VITE_API_BASE_URL` = כתובת ה-Backend שקיבלתם מ-Render (למשל `https://careerfit-backend.onrender.com`)
5. לחצו **Deploy**.

---

## 7. הגבלות ידועות ב-Render

> **חשוב:** Render משתמש ב-Ephemeral Filesystem.

- קובץ `careerfit.db` שנוצר בזמן ריצה **יימחק** כאשר השירות מתחדש.
- לפרויקט אקדמי מקומי — אין בעיה.
- לפריסה ייצורית — יש להעביר ל-PostgreSQL או להשתמש ב-Render Disk.

### פתרון עתידי:
```python
# בעתיד — DATABASE_URL ל-PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", None)
if DATABASE_URL:
    # Use SQLAlchemy + PostgreSQL
else:
    # Use SQLite locally
```

---

## 8. בדיקת הפריסה

- Backend: `https://YOUR-BACKEND.onrender.com/health`
- Frontend: `https://YOUR-FRONTEND.onrender.com`
- API docs: `https://YOUR-BACKEND.onrender.com/docs`
