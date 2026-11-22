#!/usr/bin/env python3
"""Download TSP's 5 days export and merge it into a historical CSV."""

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import fcntl
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

URL = "https://www.tsp.gov/share-price-history/"
CORE_FUNDS = {"G Fund", "F Fund", "C Fund", "S Fund", "I Fund"}
FIVE_DAYS = re.compile(r"(?:last\s+)?5\s+days?", re.I)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%b %d, %Y").date()


def read_prices(path: Path, *, recent: bool = False):
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source, strict=True)
        header = [column.strip() for column in next(reader, [])]
        funds = header[1:]
        if len(set(funds)) != len(funds) or not CORE_FUNDS.issubset(funds):
            raise ValueError(f"{path.name} has missing or duplicate fund columns.")
        if recent and not FIVE_DAYS.fullmatch(header[0]):
            raise ValueError(f"Expected a 5 days export, got {header[0]!r}.")

        prices = {}
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            if len(row) != len(header):
                raise ValueError(f"{path.name} has an invalid row at line {reader.line_num}.")
            price_date = parse_date(row[0].strip())
            if price_date in prices:
                raise ValueError(f"{path.name} repeats {price_date}.")
            values = dict(zip(funds, (cell.strip() for cell in row[1:])))
            for fund, value in values.items():
                if value or fund in CORE_FUNDS:
                    try:
                        price = Decimal(value)
                        if not price.is_finite() or price <= 0:
                            raise InvalidOperation
                    except InvalidOperation:
                        raise ValueError(f"Invalid price for {fund} on {price_date}.") from None
            prices[price_date] = values

    if not prices:
        raise ValueError(f"{path.name} contains no price rows.")
    return funds, prices


def download_csv(output: Path, headless: bool) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page(accept_downloads=True)
        page.set_default_timeout(20_000)
        response = page.goto(URL, wait_until="domcontentloaded", timeout=30_000)
        if response is not None and not response.ok:
            raise ValueError(f"TSP returned HTTP {response.status}.")

        page.get_by_text("All share prices", exact=True).filter(visible=True).first.click()
        time_frame = page.get_by_text("Time frame", exact=True).filter(visible=True)
        time_frame.click()
        page.get_by_text("5 days", exact=True).filter(visible=True).click()
        applied_filter = re.compile(r"^From (?:Last )?5 Days$", re.I)
        page.get_by_text(applied_filter).filter(visible=True).wait_for()
        page.get_by_text("Actions", exact=True).filter(visible=True).click()

        with page.expect_download(timeout=30_000) as pending:
            page.get_by_text("Download CSV", exact=True).filter(visible=True).click()

        pending.value.save_as(output)


def merge_history(export: Path, history: Path, candidate: Path) -> bool:
    recent_funds, recent_prices = read_prices(export, recent=True)
    if history.exists():
        funds, prices = read_prices(history)
    else:
        funds, prices = [], {}

    funds.extend(fund for fund in recent_funds if fund not in funds)
    for price_date, values in recent_prices.items():
        prices.setdefault(price_date, {}).update(values)

    with candidate.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(["Date", *funds])
        for price_date, values in sorted(prices.items()):
            writer.writerow([price_date.isoformat(), *(values.get(fund, "") for fund in funds)])

    if history.exists() and candidate.read_bytes() == history.read_bytes():
        return False
    candidate.replace(history)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("tsp-share-price-history.csv"))
    parser.add_argument("--headless", action="store_true", help="Hide the browser window.")
    args = parser.parse_args()
    try:
        from playwright.sync_api import Error as PlaywrightError
    except ImportError:
        parser.exit(1, "Install Playwright with python3 -m pip install --upgrade playwright.\n")

    history = args.output.resolve()
    try:
        history.parent.mkdir(parents=True, exist_ok=True)
        # Lock the output directory without leaving a lock file in the repository.
        with TemporaryDirectory(dir=history.parent) as temporary:
            lock = os.open(history.parent, os.O_RDONLY)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX)
                export = Path(temporary) / "download.csv"
                download_csv(export, args.headless)
                changed = merge_history(export, history, Path(temporary) / "merged.csv")
            finally:
                os.close(lock)
    except (PlaywrightError, OSError, ValueError, csv.Error) as error:
        parser.exit(1, f"TSP update failed: {error}\n")
    print(f"{'Updated' if changed else 'No changes to'} {history}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
