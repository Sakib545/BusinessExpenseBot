import json
import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


load_dotenv()

DEFAULT_CATEGORIES = (
    "নারিকেল তেলের টাকা",
    "স্টিকারের টাকা",
    "বোতলের টাকা",
    "তেলের টাকা",
    "পলির টাকা",
    "বক্সের টাকা",
    "বেতন",
)


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", "").strip())
    allowed_user_ids_raw: str = field(
        default_factory=lambda: os.getenv("ALLOWED_USER_IDS", "")
    )
    spreadsheet_id: str = field(
        default_factory=lambda: os.getenv("SPREADSHEET_ID", "").strip()
    )
    worksheet_name: str = field(
        default_factory=lambda: os.getenv("WORKSHEET_NAME", "Expenses").strip()
    )
    credentials_json: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    )
    timezone_name: str = field(
        default_factory=lambda: os.getenv("TIMEZONE", "Asia/Dhaka").strip()
    )
    categories: tuple[str, ...] = DEFAULT_CATEGORIES

    @property
    def allowed_user_ids(self) -> frozenset[int]:
        try:
            return frozenset(
                int(value.strip())
                for value in self.allowed_user_ids_raw.split(",")
                if value.strip()
            )
        except ValueError as exc:
            raise ValueError("ALLOWED_USER_IDS-এ শুধু Telegram numeric ID দিন") from exc

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def credentials(self) -> dict:
        try:
            return json.loads(self.credentials_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_CREDENTIALS_JSON সঠিক JSON নয়") from exc

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if len(self.allowed_user_ids) != 2:
            missing.append("ALLOWED_USER_IDS (ঠিক ২টি ID)")
        if not self.spreadsheet_id:
            missing.append("SPREADSHEET_ID")
        if not self.credentials_json:
            missing.append("GOOGLE_CREDENTIALS_JSON")
        if missing:
            raise ValueError("Missing/invalid environment variables: " + ", ".join(missing))
        _ = self.credentials
        _ = self.timezone


settings = Settings()
