"""
Модуль экспорта результатов парсинга в Excel (XLSX).
Создаёт файл с автофильтрами, форматированием, итоговым листом статистики.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import openpyxl
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from app.models import ContactRecord, ParseTask, SocialLinks

logger = logging.getLogger(__name__)

# ── Определение колонок ────────────────────────────────────────────────────────────

COLUMNS: list[dict[str, Any]] = [
    {"key": "company_name",         "header": "Название компании",        "width": 30},
    {"key": "site_url",             "header": "Сайт",                     "width": 35},
    {"key": "company_email",        "header": "Общий email",              "width": 30},
    {"key": "position_raw",         "header": "Должность (как на сайте)", "width": 35},
    {"key": "position_normalized",  "header": "Должность (норм.)",        "width": 30},
    {"key": "full_name",            "header": "ФИО",                      "width": 28},
    {"key": "personal_email",       "header": "Личный email",             "width": 30},
    {"key": "phone",                "header": "Телефон",                  "width": 18},
    {"key": "inn",                  "header": "ИНН",                      "width": 14},
    {"key": "kpp",                  "header": "КПП",                      "width": 12},
    {"key": "social_vk",            "header": "ВКонтакте",                "width": 30},
    {"key": "social_telegram",      "header": "Telegram",                 "width": 25},
    {"key": "social_linkedin",      "header": "LinkedIn",                 "width": 30},
    {"key": "social_other",         "header": "Соцсети (прочие)",         "width": 30},
    {"key": "source_url",           "header": "URL-источник",             "width": 40},
    {"key": "page_language",        "header": "Язык страницы",            "width": 12},
    {"key": "scan_date",            "header": "Дата сканирования",        "width": 20},
    {"key": "extraction_variant",   "header": "Вариант",                  "width": 10},
    {"key": "status",               "header": "Статус",                   "width": 12},
    {"key": "comment",              "header": "Комментарий",              "width": 40},
]

# ── Цвета темы ────────────────────────────────────────────────────────────────────

COLOR_HEADER_BG    = "1E3A5F"   # Тёмно-синий заголовок
COLOR_HEADER_FONT  = "FFFFFF"   # Белый текст заголовка
COLOR_ROW_ODD      = "FFFFFF"   # Белый
COLOR_ROW_EVEN     = "F0F4FA"   # Светло-голубой
COLOR_COMPANY_BG   = "D6E4F0"   # Акцент смены компании
COLOR_ERROR_BG     = "FFF0F0"   # Светло-красный для ошибок
COLOR_SUMMARY_BG   = "E8F5E9"   # Светло-зелёный для сводки

# ── Шрифты ─────────────────────────────────────────────────────────────────────────────

FONT_HEADER  = Font(name="Calibri", size=10, bold=True, color=COLOR_HEADER_FONT)
FONT_BODY    = Font(name="Calibri", size=10)
FONT_LINK    = Font(name="Calibri", size=10, color="0563C1", underline="single")
FONT_SUMMARY = Font(name="Calibri", size=11, bold=True)


def _cell_border() -> Border:
    """Тонкая граница для ячеек."""
    thin = Side(style="thin", color="CCCCCC")
    return Border(left=thin, right=thin, top=thin, bottom=thin)


class ExcelExporter:
    """
    Экспортирует результаты парсинга в Excel-файл с форматированием.
    """

    async def export(
        self,
        results: list[dict[str, Any]],
        task: ParseTask,
        output_dir: Path,
    ) -> Path:
        """
        Создаёт XLSX-файл с результатами парсинга.

        Args:
            results: Список словарей {site_url, company_name, contacts: [ContactRecord]}.
            task: Задача парсинга (для метаданных).
            output_dir: Директория для сохранения файла.

        Returns:
            Path к созданному файлу.
        """
        wb = openpyxl.Workbook()

        # Лист 1: Контакты
        ws_contacts = wb.active
        ws_contacts.title = "Контакты"
        self._build_contacts_sheet(ws_contacts, results)

        # Лист 2: Статистика
        ws_stats = wb.create_sheet("Статистика")
        self._build_stats_sheet(ws_stats, results, task)

        # Лист 3: Лог обработки
        ws_log = wb.create_sheet("Лог")
        self._build_log_sheet(ws_log, results, task)

        # Сохраняем файл
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        task_short = str(task.task_id)[:8]
        filename = f"Результаты_парсинга_{timestamp}_{task_short}.xlsx"
        filepath = output_dir / filename

        wb.save(str(filepath))
        logger.info("Excel сохранён: %s (%.1f KB)", filepath, filepath.stat().st_size / 1024)
        return filepath

    def _build_contacts_sheet(
        self,
        ws,
        results: list[dict[str, Any]],
    ) -> None:
        """Заполняет лист «Контакты»."""
        headers = [col["header"] for col in COLUMNS]
        ws.append(headers)

        header_fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        for cell in ws[1]:
            cell.font = FONT_HEADER
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = _cell_border()

        ws.row_dimensions[1].height = 32

        row_idx = 2
        current_company = None

        for site_result in results:
            contacts: list[ContactRecord] = site_result.get("contacts", [])
            if not contacts:
                continue

            for contact in contacts:
                row_data = self._contact_to_row(contact)
                ws.append(row_data)

                is_new_company = contact.company_name != current_company
                if is_new_company:
                    current_company = contact.company_name
                    bg_color = COLOR_COMPANY_BG
                else:
                    bg_color = COLOR_ROW_EVEN if row_idx % 2 == 0 else COLOR_ROW_ODD

                row_fill = PatternFill("solid", fgColor=bg_color)
                row_error = contact.status == "error"

                for col_idx, cell in enumerate(ws[row_idx], 1):
                    cell.font = FONT_BODY
                    cell.fill = PatternFill("solid", fgColor=COLOR_ERROR_BG) if row_error else row_fill
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    cell.border = _cell_border()

                    col_key = COLUMNS[col_idx - 1]["key"]
                    if col_key in ("site_url", "source_url") and cell.value:
                        cell.hyperlink = str(cell.value)
                        cell.font = FONT_LINK
                    elif col_key in ("company_email", "personal_email") and cell.value:
                        cell.hyperlink = f"mailto:{cell.value}"
                        cell.font = FONT_LINK
                    elif col_key in ("social_vk", "social_telegram", "social_linkedin") and cell.value:
                        cell.hyperlink = str(cell.value)
                        cell.font = FONT_LINK

                row_idx += 1

        for i, col_def in enumerate(COLUMNS, 1):
            col_letter = get_column_letter(i)
            ws.column_dimensions[col_letter].width = col_def["width"]

        for row in range(2, row_idx):
            ws.row_dimensions[row].height = 20

        ws.freeze_panes = "A2"

        if row_idx > 2:
            last_col = get_column_letter(len(COLUMNS))
            ws.auto_filter.ref = f"A1:{last_col}{row_idx - 1}"

        if row_idx > 2:
            table = Table(
                displayName="Контакты",
                ref=f"A1:{get_column_letter(len(COLUMNS))}{row_idx - 1}",
            )
            style = TableStyleInfo(
                name="TableStyleMedium2",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=True,
                showColumnStripes=False,
            )
            table.tableStyleInfo = style
            ws.add_table(table)

    def _build_stats_sheet(
        self,
        ws,
        results: list[dict[str, Any]],
        task: ParseTask,
    ) -> None:
        """Заполняет лист «Статистика»."""
        fill_header = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        fill_value  = PatternFill("solid", fgColor=COLOR_SUMMARY_BG)

        def add_row(label: str, value: Any) -> None:
            ws.append([label, value])
            row = ws.max_row
            ws.cell(row, 1).font = Font(name="Calibri", size=11, bold=True)
            ws.cell(row, 2).font = Font(name="Calibri", size=11)
            ws.cell(row, 1).fill = PatternFill("solid", fgColor="EEF2F7")
            ws.cell(row, 2).fill = fill_value
            ws.cell(row, 1).border = _cell_border()
            ws.cell(row, 2).border = _cell_border()

        def add_header(title: str) -> None:
            ws.append([title])
            row = ws.max_row
            cell = ws.cell(row, 1)
            cell.font = FONT_HEADER
            cell.fill = fill_header
            cell.alignment = Alignment(horizontal="left", vertical="center")
            ws.merge_cells(f"A{row}:B{row}")
            ws.row_dimensions[row].height = 24

        ws.column_dimensions["A"].width = 35
        ws.column_dimensions["B"].width = 30

        add_header("📊 Итоги парсинга")

        total_contacts = sum(len(r.get("contacts", [])) for r in results)
        total_sites = len(results)
        successful_sites = sum(1 for r in results if r.get("contacts"))

        add_row("Дата создания задачи", task.created_at.strftime("%d.%m.%Y %H:%M:%S"))
        add_row("Дата завершения", task.finished_at.strftime("%d.%m.%Y %H:%M:%S") if task.finished_at else "—")
        add_row("Режим парсинга", f"Режим {task.mode.value}")
        add_row("Вариант извлечения", task.variant.value)
        add_row("Всего сайтов обработано", total_sites)
        add_row("Сайтов с результатами", successful_sites)
        add_row("Итого контактов найдено", total_contacts)
        add_row("Ошибок и предупреждений", task.progress.errors)
        add_row("Просмотрено страниц", task.progress.total_pages)

        if task.progress.elapsed_seconds > 0:
            duration = task.progress.elapsed_seconds
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            add_row("Время выполнения", f"{minutes} мин {seconds} сек")

        if task.variant.value == "B":
            add_row("Токенов LLM использовано", task.progress.llm_tokens_used)
            add_row("Переключений на Вариант A", task.progress.fallback_count)

        ws.append([])
        add_header("📋 Результаты по сайтам")
        ws.append(["Сайт", "Контактов найдено"])
        header_row = ws.max_row
        for cell in ws[header_row]:
            cell.font = Font(name="Calibri", size=10, bold=True, color=COLOR_HEADER_FONT)
            cell.fill = PatternFill("solid", fgColor="3D7AB5")

        for site_result in sorted(results, key=lambda r: -len(r.get("contacts", []))):
            ws.append([
                site_result.get("site_url", ""),
                len(site_result.get("contacts", [])),
            ])

        ws.append([])
        add_header("👥 Топ должностей")
        ws.append(["Должность", "Количество"])
        ws.cell(ws.max_row, 1).font = Font(name="Calibri", size=10, bold=True, color=COLOR_HEADER_FONT)
        ws.cell(ws.max_row, 2).font = Font(name="Calibri", size=10, bold=True, color=COLOR_HEADER_FONT)
        ws.cell(ws.max_row, 1).fill = PatternFill("solid", fgColor="3D7AB5")
        ws.cell(ws.max_row, 2).fill = PatternFill("solid", fgColor="3D7AB5")

        position_counts: dict[str, int] = {}
        for r in results:
            for c in r.get("contacts", []):
                if isinstance(c, ContactRecord):
                    pos = c.position_normalized or c.position_raw or "Не указана"
                else:
                    pos = "Не указана"
                position_counts[pos] = position_counts.get(pos, 0) + 1

        for pos, count in sorted(position_counts.items(), key=lambda x: -x[1])[:30]:
            ws.append([pos, count])

    def _build_log_sheet(
        self,
        ws,
        results: list[dict[str, Any]],
        task: ParseTask,
    ) -> None:
        """Заполняет лист «Лог» с информацией об обработке."""
        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 50
        ws.column_dimensions["C"].width = 20
        ws.column_dimensions["D"].width = 60

        ws.append(["Время", "Сайт", "Страниц", "Статус / Примечание"])
        header_fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        for cell in ws[1]:
            cell.font = FONT_HEADER
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for site_result in results:
            contacts_count = len(site_result.get("contacts", []))
            status = "OK" if contacts_count > 0 else "Нет контактов"
            ws.append([
                datetime.utcnow().strftime("%d.%m.%Y %H:%M"),
                site_result.get("site_url", ""),
                site_result.get("pages_crawled", 0),
                f"{status}: найдено {contacts_count} контактов",
            ])

    @staticmethod
    def _contact_to_row(contact: ContactRecord) -> list[Any]:
        """Преобразует ContactRecord в строку для вставки в лист."""
        social = contact.social_links or SocialLinks()

        other_social = ", ".join(filter(None, [
            social.facebook,
            social.instagram,
            social.twitter,
            social.youtube,
            social.ok,
        ]))

        scan_date_str = ""
        if contact.scan_date:
            try:
                scan_date_str = contact.scan_date.strftime("%d.%m.%Y %H:%M")
            except Exception:
                scan_date_str = str(contact.scan_date)

        return [
            contact.company_name or "",
            contact.site_url or "",
            contact.company_email or "",
            contact.position_raw or "",
            contact.position_normalized or "",
            contact.full_name or "",
            contact.personal_email or "",
            contact.phone or contact.phone_raw or "",
            contact.inn or "",
            contact.kpp or "",
            social.vk or "",
            social.telegram or "",
            social.linkedin or "",
            other_social,
            contact.source_url or "",
            contact.page_language or "",
            scan_date_str,
            contact.extraction_variant.value if contact.extraction_variant else "A",
            contact.status or "ok",
            contact.comment or "",
        ]
