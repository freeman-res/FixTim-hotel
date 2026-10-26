import pandas as pd
import glob
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
OUT_FILE = ROOT_DIR / "dataset_report.txt"

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.max_colwidth', 30)

def main():
    csv_files = glob.glob(str(RAW_DIR / "**" / "*.csv"), recursive=True)
    
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Найдено файлов: {len(csv_files)}\n")
        
        for file_path in csv_files:
            file_name = os.path.relpath(file_path, RAW_DIR)
            f.write(f"\n{'='*80}\n")
            f.write(f"ФАЙЛ: {file_name}\n")
            f.write(f"{'='*80}\n")
            
            try:
                # Читаем только 100 строк для анализа структуры (чтобы не ждать вечно)
                df = pd.read_csv(file_path, low_memory=False, nrows=100)
                
                # Размер файла целиком (считаем строки быстро)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as count_f:
                    total_rows = sum(1 for _ in count_f) - 1
                
                f.write(f"РАЗМЕР: ~{total_rows} строк, {df.shape[1]} колонок\n\n")
                
                f.write("КОЛОНКИ И ТИПЫ:\n")
                f.write(df.dtypes.to_string() + "\n\n")
                
                f.write("ПЕРВЫЕ 2 СТРОКИ:\n")
                f.write(df.head(2).to_string() + "\n\n")
                
                f.write("ПРОПУСКИ (ТОП-5):\n")
                missing = df.isna().sum()
                missing = missing[missing > 0].sort_values(ascending=False)
                if not missing.empty:
                    f.write(missing.head(5).to_string() + "\n")
                else:
                    f.write("Нет пропусков в первых 100 строках.\n")
                    
            except Exception as e:
                f.write(f"ОШИБКА: {e}\n")

    print(f"Готово! Отчет сохранен в {OUT_FILE}")

if __name__ == "__main__":
    main() 