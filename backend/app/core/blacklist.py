"""
Модуль управления чёрным списком (opt-out).
Хранит домены, email-адреса и ИНН, которые должны быть исключены из парсинга.
Поддерживает загрузку из файлов и проверку в режиме реального времени.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Путь к файлу постоянного хранения чёрного списка
_BLACKLIST_FILE = Path("blacklist_store.json")


class BlacklistManager:
    """
    Менеджер чёрного списка для исключения нежелательных доменов,
    email-адресов и ИНН из парсинга.
    """

    def __init__(self) -> None:
        self._domains: set[str] = set()   # нормализованные домены (без www)
        self._emails: set[str] = set()    # email-адреса в нижнем регистре
        self._inns: set[str] = set()      # ИНН (строки цифр)
        self._load_from_disk()

    async def load_from_file(self, content: bytes, filename: str) -> int:
        """
        Загружает чёрный список из загруженного файла.
        Возвращает количество добавленных новых записей.
        """
        added = 0
        lower = filename.lower()

        if lower.endswith((".xlsx", ".xls")):
            added = self._load_from_excel(content)
        elif lower.endswith(".csv"):
            added = self._load_from_csv(content)
        elif lower.endswith(".json"):
            added = self._load_from_json_bytes(content)
        else:
            added = self._load_from_text(content)

        if added > 0:
            self._save_to_disk()

        logger.info("Загружено %d новых записей в чёрный список из %s", added, filename)
        return added

    def _load_from_text(self, content: bytes) -> int:
        added = 0
        text = content.decode("utf-8-sig", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if self._add_entry(line):
                added += 1
        return added

    def _load_from_csv(self, content: bytes) -> int:
        added = 0
        try:
            text = content.decode("utf-8-sig", errors="replace")
            reader = csv.reader(io.StringIO(text))
            for row in reader:
                for cell in row:
                    cell = cell.strip()
                    if cell and not cell.startswith("#"):
                        if self._add_entry(cell):
                            added += 1
        except Exception as exc:
            logger.error("Ошибка чтения CSV для чёрного списка: %s", exc)
        return added

    def _load_from_excel(self, content: bytes) -> int:
        added = 0
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    for cell in row:
                        if cell is not None:
                            val = str(cell).strip()
                            if val and not val.startswith("#"):
                                if self._add_entry(val):
                                    added += 1
        except Exception as exc:
            logger.error("Ошибка чтения Excel для чёрного списка: %s", exc)
        return added

    def _load_from_json_bytes(self, content: bytes) -> int:
        added = 0
        try:
            data = json.loads(content.decode("utf-8-sig", errors="replace"))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str) and item.strip():
                        if self._add_entry(item.strip()):
                            added += 1
            elif isinstance(data, dict):
                for key in ("domains", "emails", "inns"):
                    for item in data.get(key, []):
                        if isinstance(item, str) and item.strip():
                            if self._add_entry(item.strip()):
                                added += 1
        except Exception as exc:
            logger.error("Ошибка чтения JSON для чёрного списка: %s", exc)
        return added

    def _add_entry(self, value: str) -> bool:
        if re.match(r"^https?://", value, re.I):
            try:
                parsed = urlparse(value)
                domain = self._normalize_domain(parsed.netloc or parsed.path)
                if domain and domain not in self._domains:
                    self._domains.add(domain)
                    return True
                return False
            except Exception:
                pass

        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            normalized = value.lower()
            if normalized not in self._emails:
                self._emails.add(normalized)
                return True
            return False

        if re.match(r"^\d{10}$|^\d{12}$", value):
            if value not in self._inns:
                self._inns.add(value)
                return True
            return False

        domain = self._normalize_domain(value)
        if domain:
            if domain not in self._domains:
                self._domains.add(domain)
                return True
        return False

    @staticmethod
    def _normalize_domain(raw: str) -> Optional[str]:
        if not raw:
            return None
        domain = raw.strip().lower()
        domain = domain.split("/")[0]
        domain = domain.split(":")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        if "." not in domain or len(domain) < 4:
            return None
        return domain

    def add_domain(self, domain: str) -> None:
        normalized = self._normalize_domain(domain)
        if normalized:
            self._domains.add(normalized)
            self._save_to_disk()

    def add_email(self, email: str) -> None:
        self._emails.add(email.lower().strip())
        self._save_to_disk()

    def add_inn(self, inn: str) -> None:
        self._inns.add(inn.strip())
        self._save_to_disk()

    def clear(self) -> None:
        self._domains.clear()
        self._emails.clear()
        self._inns.clear()
        self._save_to_disk()
        logger.info("Чёрный список очищен")

    def is_domain_blocked(self, url_or_domain: str) -> bool:
        if not url_or_domain:
            return False
        if url_or_domain.startswith(("http://", "https://")):
            try:
                parsed = urlparse(url_or_domain)
                domain = self._normalize_domain(parsed.netloc)
            except Exception:
                return False
        else:
            domain = self._normalize_domain(url_or_domain)

        if not domain:
            return False

        parts = domain.split(".")
        for i in range(len(parts) - 1):
            candidate = ".".join(parts[i:])
            if candidate in self._domains:
                return True
        return False

    def is_email_blocked(self, email: str) -> bool:
        if not email:
            return False
        normalized = email.lower().strip()
        if normalized in self._emails:
            return True
        if "@" in normalized:
            domain = normalized.split("@", 1)[1]
            return self.is_domain_blocked(domain)
        return False

    def is_inn_blocked(self, inn: str) -> bool:
        return inn.strip() in self._inns

    def is_blocked(self, url: Optional[str] = None, email: Optional[str] = None, inn: Optional[str] = None) -> bool:
        if url and self.is_domain_blocked(url):
            return True
        if email and self.is_email_blocked(email):
            return True
        if inn and self.is_inn_blocked(inn):
            return True
        return False

    def count(self, category: str) -> int:
        mapping = {"domains": self._domains, "emails": self._emails, "inns": self._inns}
        return len(mapping.get(category, set()))

    def total_count(self) -> int:
        return len(self._domains) + len(self._emails) + len(self._inns)

    def _save_to_disk(self) -> None:
        try:
            data = {
                "domains": sorted(self._domains),
                "emails": sorted(self._emails),
                "inns": sorted(self._inns),
            }
            _BLACKLIST_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Ошибка сохранения чёрного списка: %s", exc)

    def _load_from_disk(self) -> None:
        if not _BLACKLIST_FILE.exists():
            return
        try:
            data = json.loads(_BLACKLIST_FILE.read_text(encoding="utf-8"))
            self._domains = set(data.get("domains", []))
            self._emails = set(data.get("emails", []))
            self._inns = set(data.get("inns", []))
            logger.info(
                "Загружен чёрный список: доменов=%d, email=%d, ИНН=%d",
                len(self._domains),
                len(self._emails),
                len(self._inns),
            )
        except Exception as exc:
            logger.error("Ошибка загрузки чёрного списка с диска: %s", exc)


# Синглтон менеджера чёрного списка
blacklist_manager = BlacklistManager()
