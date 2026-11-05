from gzip import GzipFile
from pathlib import Path
from tarfile import open as open_tar


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "catalog"
OUTPUT = ROOT / "data" / "catalog_bundle.tar.gz"


def main() -> int:
    files = sorted(SOURCE.glob("*.json"))
    if not files or not (SOURCE / "hotels.json").is_file():
        raise RuntimeError("Hotel catalog is missing")
    with OUTPUT.open("wb") as target:
        with GzipFile(fileobj=target, mode="wb", filename="", mtime=0, compresslevel=6) as compressed:
            with open_tar(fileobj=compressed, mode="w") as archive:
                for path in files:
                    info = archive.gettarinfo(path, arcname=f"catalog/{path.name}")
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    with path.open("rb") as source:
                        archive.addfile(info, source)
    print(f"PASS: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes; {len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
