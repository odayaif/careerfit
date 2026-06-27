"""
data_inspector.py — Stage 1: Inspect archive.zip and generate Hebrew inventory report.
Run standalone: python backend/data_inspector.py
"""
import zipfile
import os
import sys
import pandas as pd
import io
import datetime

# Paths
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_HERE)
ZIP_PATH = os.path.join(PROJECT_ROOT, "data", "archive.zip")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
REPORT_PATH = os.path.join(REPORTS_DIR, "data_inventory.md")

ENCODINGS = ["utf-8", "utf-8-sig", "cp1255", "iso-8859-8", "latin1"]


def try_read_csv(zip_file: zipfile.ZipFile, name: str, nrows: int = 200) -> pd.DataFrame:
    """Try reading a CSV from the ZIP with multiple encodings."""
    for enc in ENCODINGS:
        try:
            with zip_file.open(name) as f:
                raw = f.read()
            df = pd.read_csv(
                io.BytesIO(raw),
                nrows=nrows,
                encoding=enc,
                on_bad_lines="skip",
                low_memory=False,
            )
            return df, enc
        except Exception:
            continue
    return pd.DataFrame(), "unknown"


def count_rows(zip_file: zipfile.ZipFile, name: str) -> int:
    """Count lines minus header."""
    try:
        with zip_file.open(name) as f:
            count = sum(1 for _ in f) - 1
        return count
    except Exception:
        return -1


def missing_pct(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    total = len(df)
    return {col: round(df[col].isna().sum() / total * 100, 1) for col in df.columns}


def run_inspection() -> str:
    """Run full inspection and return the markdown report string."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    lines = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# דו\"ח בדיקת נתונים — CareerFit")
    lines.append(f"\n**תאריך:** {now}\n")

    if not os.path.exists(ZIP_PATH):
        lines.append("## שגיאה: קובץ הדאטה לא נמצא")
        lines.append(f"\nנתיב מצופה: `{ZIP_PATH}`")
        lines.append("\nהמערכת תפעל במצב דמו. יש להוסיף את `data/archive.zip` ולהריץ מחדש.")
        report = "\n".join(lines)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report)
        print("⚠️  archive.zip לא נמצא — נוצר דו\"ח placeholder.")
        return report

    lines.append(f"**נתיב ZIP:** `{ZIP_PATH}`")
    lines.append(f"**גודל ZIP:** {os.path.getsize(ZIP_PATH) / 1_048_576:.1f} MB\n")

    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        all_files = z.namelist()
        csv_files = [f for f in all_files if f.lower().endswith(".csv")]

        lines.append(f"## תוכן הארכיון\n")
        lines.append(f"**סך קבצים:** {len(all_files)}")
        lines.append(f"**קבצי CSV:** {len(csv_files)}\n")
        lines.append("| שם קובץ | גודל (MB) |")
        lines.append("|---------|-----------|")
        for info in z.infolist():
            if info.filename.endswith(".csv"):
                lines.append(f"| `{info.filename}` | {info.file_size/1_048_576:.2f} |")

        lines.append("\n---\n")
        lines.append("## פירוט קבצי CSV\n")

        for csv_name in csv_files:
            lines.append(f"### `{csv_name}`\n")
            df, enc = try_read_csv(z, csv_name)
            row_count = count_rows(z, csv_name)

            lines.append(f"- **קידוד:** {enc}")
            lines.append(f"- **שורות (הערכה):** {row_count:,}")
            lines.append(f"- **עמודות:** {len(df.columns)}")

            if not df.empty:
                lines.append(f"- **שמות עמודות:** {', '.join(df.columns.tolist())}")
                mp = missing_pct(df)
                missing_cols = {k: v for k, v in mp.items() if v > 0}
                if missing_cols:
                    lines.append("- **ערכים חסרים (בדגימה):**")
                    for col, pct in sorted(missing_cols.items(), key=lambda x: -x[1])[:10]:
                        lines.append(f"  - `{col}`: {pct}%")
                lines.append("\n**שורות לדוגמה:**\n")
                lines.append("```")
                lines.append(df.head(3).to_string(max_colwidth=80))
                lines.append("```")
            else:
                lines.append("- ⚠️ לא ניתן לקרוא את הקובץ")
            lines.append("")

    report = "\n".join(lines)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ דו\"ח בדיקת נתונים נשמר: {REPORT_PATH}")
    return report


if __name__ == "__main__":
    run_inspection()
    print("סיום בדיקת נתונים.")
