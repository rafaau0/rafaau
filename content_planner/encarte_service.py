"""Ponte para a automação de encartes PSD já validada no projeto Liderança."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

ROOT_DIR = Path(__file__).resolve().parent.parent
LEGACY_DIR = ROOT_DIR.parent / "AUTOMAÇÃO LIDERANÇA - FUNCIONAL V.1.0.0"


def _load():
    if not (LEGACY_DIR / "app").is_dir():
        raise RuntimeError("A pasta da Automação Liderança não foi encontrada ao lado do Neiva Planner.")
    legacy_path = str(LEGACY_DIR)
    if legacy_path not in sys.path:
        sys.path.insert(0, legacy_path)
    from app.core.excel import ExcelReader
    from app.core.image_match import ImageMatcher
    from app.core.logger import build_logger
    from app.core.photoshop import PhotoshopAutomation
    from app.core.photo_extractor import PhotoExtractor
    from app.core.validator import Validator
    return ExcelReader, ImageMatcher, build_logger, PhotoshopAutomation, PhotoExtractor, Validator


def prepare(psd: Path, spreadsheet: Path, photos_dir: Path, output_dir: Path):
    ExcelReader, ImageMatcher, _, _, _, Validator = _load()
    products = ExcelReader().read_products(spreadsheet)
    ImageMatcher(ROOT_DIR / "database" / "encarte_image_cache.json").match(products, photos_dir)
    return products, Validator().validate(psd, spreadsheet, photos_dir, products, output_dir)


def generate(psd: Path, products, offer_period: str, output_dir: Path, progress: Callable[[int, str], None]) -> Path:
    _, _, build_logger, PhotoshopAutomation, _, _ = _load()
    logger = build_logger(ROOT_DIR / "exports" / "encartes" / "logs")
    progress(50, "Preparando arquivo de saída…")
    result = PhotoshopAutomation(logger, progress).generate(psd, products, offer_period, output_dir)
    progress(100, "Encarte gerado.")
    return result


def extract_photos(psd: Path, photos_dir: Path, progress: Callable[[int, str], None]) -> list[Path]:
    _, _, build_logger, _, PhotoExtractor, _ = _load()
    return PhotoExtractor(build_logger(ROOT_DIR / "exports" / "encartes" / "logs"), progress).extract(psd, photos_dir)


def export_files(psd: Path) -> tuple[Path, Path]:
    _, _, build_logger, _, _, _ = _load()
    from app.core.exporter import Exporter
    return Exporter(build_logger(ROOT_DIR / "exports" / "encartes" / "logs")).export(psd)
