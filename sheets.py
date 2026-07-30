from datetime import datetime
from threading import Lock

import gspread
from google.oauth2.service_account import Credentials

from config import Settings


SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)
HEADERS = ["Date", "Category", "Amount"]


class GoogleSheetStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._worksheet = None
        self._lock = Lock()

    def _connect(self):
        credentials = Credentials.from_service_account_info(
            self.settings.credentials, scopes=SCOPES
        )
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(self.settings.spreadsheet_id)
        try:
            return spreadsheet.worksheet(self.settings.worksheet_name)
        except gspread.WorksheetNotFound:
            return spreadsheet.add_worksheet(
                title=self.settings.worksheet_name, rows=1000, cols=3
            )

    @property
    def worksheet(self):
        if self._worksheet is None:
            self._worksheet = self._connect()
        return self._worksheet

    def ensure_sheet(self) -> None:
        with self._lock:
            first_row = self.worksheet.row_values(1)
            if not first_row:
                self.worksheet.append_row(HEADERS, value_input_option="USER_ENTERED")
            elif first_row[:3] != HEADERS:
                raise ValueError(
                    "Worksheet-এর প্রথম row অবশ্যই Date, Category, Amount হতে হবে"
                )
            self.worksheet.freeze(rows=1)

    def now(self) -> datetime:
        return datetime.now(self.settings.timezone)

    def add_expense(self, category: str, amount: float) -> str:
        date_text = self.now().strftime("%Y-%m-%d")
        with self._lock:
            self.worksheet.append_row(
                [date_text, category, amount], value_input_option="USER_ENTERED"
            )
        return date_text

    def _read_rows(self) -> list[dict]:
        with self._lock:
            values = self.worksheet.get_all_values()

        rows = []
        for row in values[1:]:
            if len(row) < 3:
                continue
            try:
                date_value = datetime.strptime(row[0].strip(), "%Y-%m-%d").date()
                amount = float(
                    row[2].replace(",", "").replace("৳", "").strip()
                )
            except (ValueError, TypeError):
                continue
            rows.append(
                {"date": date_value, "category": row[1].strip(), "amount": amount}
            )
        return rows

    def get_today(self) -> list[dict]:
        today = self.now().date()
        return [row for row in self._read_rows() if row["date"] == today]

    def get_month(self) -> list[dict]:
        now = self.now()
        return [
            row
            for row in self._read_rows()
            if row["date"].year == now.year and row["date"].month == now.month
        ]

    def get_all(self) -> list[dict]:
        return self._read_rows()
