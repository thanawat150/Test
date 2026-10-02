from __future__ import annotations

from pathlib import Path

from python_calamine import CalamineWorkbook


REQUIRED_SHEETS = ("Master Timeline", "Asset Map", "Track Setup")


def _trim_table(rows: list[list]) -> list[list[str]]:
    cleaned: list[list[str]] = []
    for row in rows:
        values = ["" if value is None else str(value).strip() for value in row]
        while values and not values[-1]:
            values.pop()
        if any(values):
            cleaned.append(values)
    return cleaned


def load_guide_excel(path: str | Path) -> dict:
    workbook = CalamineWorkbook.from_path(str(path))
    try:
        sheet_names = set(workbook.sheet_names)
        missing = [name for name in REQUIRED_SHEETS if name not in sheet_names]
        if missing:
            raise ValueError(
                "Excel ขาด Sheet ที่จำเป็น: " + ", ".join(missing)
            )

        master = _trim_table(
            workbook.get_sheet_by_name("Master Timeline").to_python(skip_empty_area=False)
        )
        assets = _trim_table(
            workbook.get_sheet_by_name("Asset Map").to_python(skip_empty_area=False)
        )
        tracks = _trim_table(
            workbook.get_sheet_by_name("Track Setup").to_python(skip_empty_area=False)
        )
    finally:
        workbook.close()

    if not master or not assets or not tracks:
        raise ValueError("Excel มี Sheet ว่างหรืออ่านข้อมูลไม่ได้")

    return {
        "master_headers": master[0],
        "master_timeline": master[1:],
        "asset_headers": assets[0],
        "asset_map": assets[1:],
        "track_headers": tracks[0],
        "track_setup": tracks[1:],
    }
