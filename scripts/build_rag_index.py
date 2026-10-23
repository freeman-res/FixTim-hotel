"""python scripts/build_rag_index.py
python scripts/build_rag_index.py --provider csv --hotels hotels.csv --offers offers.csv --reviews reviews.csv
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "app"))
from catalog.service import CatalogService

def main() -> None:
    parser = argparse.ArgumentParser(description="Пересборка RAG-индекса")
    parser.add_argument(
        "--provider",
        default="demo",
        choices=["demo", "json", "csv", "sql", "http"],
        help="Тип провайдера (по умолчанию: demo)" )
    parser.add_argument("--hotels", help="Путь к hotels.json/csv или URL для http")
    parser.add_argument("--offers", help="Путь к offers.json/csv")
    parser.add_argument("--reviews", help="Путь к reviews.json/csv")
    parser.add_argument("--db-path", help="Путь к SQLite базе (для provider=sql)")
    parser.add_argument("--base-url", help="Базовый URL API (для provider=http)")
    args = parser.parse_args()
    # Собираем kwargs для провайдера
    kwargs = {}
    if args.provider == "json":
        kwargs = {
            "hotels_path": args.hotels,
            "offers_path": args.offers,
            "reviews_path": args.reviews }
    elif args.provider == "csv":
        kwargs = {
            "hotels_csv": args.hotels,
            "offers_csv": args.offers,
            "reviews_csv": args.reviews}
    elif args.provider == "sql":
        kwargs = {"db_path": args.db_path}
    elif args.provider == "http":
        kwargs = {"base_url": args.base_url}
    print(f"Провайдер: {args.provider}")
    svc = CatalogService(args.provider, **kwargs)
    print("Сборка RAG-индекса...")
    n = svc.build_rag(reset=True)
    print(f"OK: проиндексировано {n} чанков")
    print("Индекс сохранён в data/vector_index/")

main()