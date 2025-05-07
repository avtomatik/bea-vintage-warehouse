import time
from zipfile import ZipFile

import duckdb
import pandas as pd
import pyarrow as pa

from core.paths import DATA_SRC_DIR, DUCKDB_PATH

# =============================================================================
# Spreadsheet geometry constants
# =============================================================================

LINE_ROW = 7

DESCRIPTION_COL = 1
SERIES_CODE_COL = 2
VALUE_START_COL = 3

DATA_START_ROWS = {
    "annual": 8,
    "quarterly": 9,
    "monthly": 9,
}

# =============================================================================
# Helpers
# =============================================================================


def clean(value):

    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value or value.lower() == "nan":
        return None

    return value


def parse_metadata(df: pd.DataFrame) -> dict:

    return {
        "table_title": clean(df.iat[0, 0]),
        "table_note": clean(df.iat[1, 0]),
        "coverage_note": clean(df.iat[2, 0]),
        "source_agency": clean(df.iat[3, 0]),
        "published_at_raw": clean(df.iat[4, 0]),
        "file_created_at_raw": clean(df.iat[5, 0]),
    }


def detect_frequency(df: pd.DataFrame) -> str | None:

    coverage = clean(df.iat[2, 0])

    if coverage is None:
        return None

    if coverage.startswith("Annual data"):
        return "annual"

    if coverage.startswith("Quarterly data"):
        return "quarterly"

    if coverage.startswith("Monthly data"):
        return "monthly"

    return None


def parse_periods(
    df: pd.DataFrame,
    frequency: str,
) -> list[tuple[int, str]]:

    periods = []

    for col_idx in range(VALUE_START_COL, len(df.columns)):

        try:

            year = int(df.iat[LINE_ROW, col_idx])

            if frequency == "annual":

                period = str(year)

            else:

                sub = int(df.iat[LINE_ROW + 1, col_idx])

                if frequency == "quarterly":
                    period = f"{year}Q{sub}"

                elif frequency == "monthly":
                    period = f"{year}M{sub:02d}"

                else:
                    continue

        except Exception:
            continue

        periods.append((col_idx, period))

    return periods


# =============================================================================
# Arrow table builder
# =============================================================================


def build_arrow_table(
    df: pd.DataFrame,
    metadata: dict,
    provenance: dict,
    frequency: str,
) -> pa.Table:

    periods = parse_periods(df, frequency)

    start_row = DATA_START_ROWS[frequency]

    columns = {
        "table_title": [],
        "table_note": [],
        "coverage_note": [],
        "source_agency": [],
        "published_at_raw": [],
        "file_created_at_raw": [],
        "frequency": [],
        "line_number": [],
        "line_description": [],
        "series_code": [],
        "period": [],
        "value": [],
        "source_archive": [],
        "source_file": [],
        "source_sheet": [],
    }

    for row_idx in range(start_row, len(df)):

        line_description = clean(df.iat[row_idx, DESCRIPTION_COL])

        # =========================================================
        # Blank line description terminates table
        # =========================================================

        if line_description is None:
            break

        line_number = clean(df.iat[row_idx, 0])

        series_code = clean(df.iat[row_idx, SERIES_CODE_COL])

        # =========================================================
        # Vectorized numeric conversion
        # =========================================================

        values = pd.to_numeric(
            df.iloc[row_idx, VALUE_START_COL:],
            errors="coerce",
        )

        for period_idx, (col_idx, period) in enumerate(periods):

            value = values.iloc[col_idx - VALUE_START_COL]

            if pd.isna(value):
                continue

            columns["table_title"].append(metadata["table_title"])

            columns["table_note"].append(metadata["table_note"])

            columns["coverage_note"].append(metadata["coverage_note"])

            columns["source_agency"].append(metadata["source_agency"])

            columns["published_at_raw"].append(metadata["published_at_raw"])

            columns["file_created_at_raw"].append(
                metadata["file_created_at_raw"]
            )

            columns["frequency"].append(frequency)

            columns["line_number"].append(line_number)

            columns["line_description"].append(line_description)

            columns["series_code"].append(series_code)

            columns["period"].append(period)

            columns["value"].append(float(value))

            columns["source_archive"].append(provenance["source_archive"])

            columns["source_file"].append(provenance["source_file"])

            columns["source_sheet"].append(provenance["source_sheet"])

    return pa.table(columns)


# =============================================================================
# DuckDB setup
# =============================================================================


def create_tables(con):

    con.execute(
        """
        create schema if not exists raw
        """
    )

    con.execute(
        """
        create table if not exists raw.bea_observations (

            table_title text,
            table_note text,
            coverage_note text,
            source_agency text,

            published_at_raw text,
            file_created_at_raw text,

            frequency text,

            line_number text,
            line_description text,
            series_code text,

            period text,
            value double,

            source_archive text,
            source_file text,
            source_sheet text
        )
        """
    )

    con.execute(
        """
        create table if not exists raw.bea_ingestion_failures (

            source_archive text,
            source_file text,
            source_sheet text,
            error_message text
        )
        """
    )


def insert_failure(
    con,
    failure: dict,
):

    con.execute(
        """
        insert into raw.bea_ingestion_failures
        values (?, ?, ?, ?)
        """,
        [
            (
                failure.get("source_archive"),
                failure.get("source_file"),
                failure.get("source_sheet"),
                failure.get("error_message"),
            )
        ],
    )


# =============================================================================
# Sheet ingestion
# =============================================================================


def ingest_sheet(
    con,
    df: pd.DataFrame,
    provenance: dict,
):

    frequency = detect_frequency(df)

    if frequency is None:
        return

    metadata = parse_metadata(df)

    arrow_table = build_arrow_table(
        df=df,
        metadata=metadata,
        provenance=provenance,
        frequency=frequency,
    )

    if arrow_table.num_rows == 0:
        return

    temp_name = "bea_arrow_batch"

    con.register(
        temp_name,
        arrow_table,
    )

    con.execute(
        f"""
        insert into raw.bea_observations
        select *
        from {temp_name}
        """
    )

    con.unregister(temp_name)

    print(f"inserted: {arrow_table.num_rows:,}")


# =============================================================================
# Main pipeline
# =============================================================================


def main():

    started_at = time.perf_counter()

    DUCKDB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "DUCKDB_PATH:",
        DUCKDB_PATH.resolve(),
    )

    con = duckdb.connect(str(DUCKDB_PATH))

    create_tables(con)

    for archive_path in sorted(DATA_SRC_DIR.iterdir()):

        print()
        print("=" * 80)
        print("archive:", archive_path.name)
        print("=" * 80)

        with ZipFile(archive_path) as archive:

            for member in archive.filelist:

                print()
                print("file:", member.filename)

                try:

                    excel = pd.ExcelFile(archive.open(member.filename))

                except Exception as e:

                    insert_failure(
                        con,
                        {
                            "source_archive": archive_path.name,
                            "source_file": member.filename,
                            "source_sheet": None,
                            "error_message": str(e),
                        },
                    )

                    continue

                for sheet_name in excel.sheet_names:

                    print("sheet:", sheet_name)

                    provenance = {
                        "source_archive": archive_path.name,
                        "source_file": member.filename,
                        "source_sheet": sheet_name,
                    }

                    try:

                        df = pd.read_excel(
                            excel,
                            sheet_name=sheet_name,
                            header=None,
                        )

                        before = time.perf_counter()

                        ingest_sheet(
                            con=con,
                            df=df,
                            provenance=provenance,
                        )

                        elapsed = time.perf_counter() - before

                        print(f"sheet processed in " f"{elapsed:.2f}s")

                    except Exception as e:

                        insert_failure(
                            con,
                            {
                                **provenance,
                                "error_message": str(e),
                            },
                        )

                        print(
                            "FAILED:",
                            e,
                        )

    elapsed = time.perf_counter() - started_at

    print()
    print("=" * 80)
    print(f"TOTAL INGESTION TIME: " f"{elapsed:.2f} seconds")
    print("=" * 80)

    con.close()


if __name__ == "__main__":
    main()
