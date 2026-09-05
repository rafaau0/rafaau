"""Automação autônoma de encartes PSD dentro do Neiva Planner."""
from __future__ import annotations

import json
import logging
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path
from typing import Callable

import openpyxl
from rapidfuzz import fuzz, process

from . import encarte_legacy as legacy
from .encarte_photo_extractor import PhotoExtractor
from .paths import EXPORTS_DIR

@dataclass(slots=True)
class OfferProduct:
    position: int
    description: str
    price: str
    image: Path | None = None
    image_score: float = 0.0
    price_error: str = ""
    image_candidate: str = ""


@dataclass(slots=True)
class ValidationReport:
    errors: list[str]
    warnings: list[str]

    @property
    def valid(self) -> bool:
        return not self.errors


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return "".join(char for char in text.lower() if char.isalnum())


def _logger() -> logging.Logger:
    folder = EXPORTS_DIR / "encartes" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("neiva_encarte")
    logger.handlers.clear(); logger.setLevel(logging.INFO)
    handler = logging.FileHandler(folder / f"encarte_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


def _parse_price(value: object) -> tuple[str, str]:
    if value is None or str(value).strip() == "":
        return "", "preço ausente ou fórmula sem valor calculado"
    if isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
    else:
        raw = str(value).strip().replace("R$", "").replace(" ", "")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        try:
            number = Decimal(raw)
        except InvalidOperation:
            return str(value).strip(), "preço não numérico"
    if not number.is_finite() or number < 0:
        return str(value).strip(), "preço negativo ou inválido"
    return f"{number.quantize(Decimal('0.01')):.2f}".replace(".", ","), ""


def _read_products(path: Path, limit: int = 25) -> list[OfferProduct]:
    if not path.is_file() or path.suffix.lower() != ".xlsx":
        raise ValueError("Selecione uma planilha XLSX válida.")
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        sheet = workbook.active
        # Alguns XLSX exportados por outros sistemas nao possuem dimensoes
        # confiaveis: max_row/max_column podem ser None. Ler as linhas reais
        # evita depender desse metadado incompleto.
        rows = sheet.iter_rows(values_only=True)
        header_row = next(rows, None)
        if not header_row:
            raise ValueError("A planilha esta vazia ou nao possui cabecalho.")
        headers = [_normalize(value).upper() for value in header_row]
        description_col = next((index + 1 for index, item in enumerate(headers) if "DESCR" in item), 0)
        price_col = next((index + 1 for index, item in enumerate(headers) if "VALOR" in item or "PRECO" in item), 0)
        if not description_col or not price_col:
            raise ValueError("A planilha precisa das colunas DESCRIÇÃO e VALOR/PREÇO.")
        products = []
        for row in rows:
            description = str((row[description_col - 1] if len(row) >= description_col else "") or "").strip()
            value = row[price_col - 1] if len(row) >= price_col else None
            price, price_error = _parse_price(value)
            if description or price:
                products.append(OfferProduct(len(products) + 1, description, price, price_error=price_error))
            if len(products) >= limit:
                break
        if not products: raise ValueError("A planilha não tem produtos preenchidos.")
        return products
    finally:
        workbook.close()


def _match_images(products: list[OfferProduct], photos_dir: Path) -> None:
    if not photos_dir.is_dir(): raise ValueError("Selecione uma pasta de fotos válida.")
    photos = [path for path in photos_dir.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    normalized = {_normalize(path.stem): path for path in photos}
    for item in products:
        key = _normalize(item.description)
        if key in normalized: item.image, item.image_score = normalized[key], 100
        elif normalized:
            result = process.extractOne(key, normalized.keys(), scorer=fuzz.token_set_ratio)
            if result and result[1] >= 95:
                item.image, item.image_score = normalized[result[0]], float(result[1])
            elif result and result[1] >= 70:
                item.image_score = float(result[1])
                item.image_candidate = normalized[result[0]].name


def prepare(psd: Path, spreadsheet: Path, photos_dir: Path, output_dir: Path):
    products = _read_products(spreadsheet); _match_images(products, photos_dir)
    errors, warnings = [], []
    if len(products) > 24:
        errors.append("A planilha possui mais de 24 produtos. Divida a oferta ou selecione explicitamente até 24 itens.")
        products = products[:24]
    if not psd.is_file(): errors.append("Selecione um modelo PSD válido.")
    try: output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc: errors.append(f"Não foi possível acessar a pasta de saída: {exc}")
    seen: dict[str, int] = {}
    for item in products:
        if not item.description: errors.append(f"Produto {item.position} sem descrição.")
        key = _normalize(item.description)
        if key in seen:
            warnings.append(f"Produto duplicado nas posições {seen[key]} e {item.position}: {item.description}")
        elif key:
            seen[key] = item.position
        if item.price_error: errors.append(f"{item.description or f'Produto {item.position}'}: {item.price_error}.")
        if not item.image:
            detail = f"; candidata incerta: {item.image_candidate} ({item.image_score:.0f}%)" if item.image_candidate else ""
            errors.append(f"Foto não confirmada: {item.description}{detail}")
        elif item.image_score < 100:
            warnings.append(f"Confirme a foto aproximada de {item.description}: {item.image.name} ({item.image_score:.0f}%).")
    return products, ValidationReport(errors, warnings)


def generate(psd: Path, products: list[OfferProduct], offer_period: str, output_dir: Path, progress: Callable[[int, str], None]) -> Path:
    if not psd.is_file(): raise ValueError("Modelo PSD não encontrado.")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = output_dir / f"{psd.stem}_preenchido_{datetime.now():%Y%m%d_%H%M%S_%f}.psd"
    data = [{"description": item.description, "price": item.price, "image": str(item.image) if item.image else ""} for item in products]
    progress(65, "Atualizando Photoshop…")
    jsx_path = Path(tempfile.gettempdir()) / f"neiva_encarte_preencher_{uuid.uuid4().hex}.jsx"
    jsx_path.write_text(legacy.build_jsx(psd, result, data, offer_period.replace("\n", "\r")), encoding="utf-8-sig")
    try:
        legacy.run_photoshop_script(legacy.find_photoshop(), jsx_path)
    except Exception:
        result.unlink(missing_ok=True)
        raise
    finally:
        jsx_path.unlink(missing_ok=True)
    if not result.is_file(): raise RuntimeError("O Photoshop terminou sem criar o PSD de saída.")
    _logger().info("PSD gerado: %s", result); progress(100, "Encarte gerado.")
    return result


def extract_photos(psd: Path, photos_dir: Path, progress: Callable[[int, str], None]) -> list[Path]:
    return PhotoExtractor(_logger(), progress).extract(psd, photos_dir)


def export_files(psd: Path) -> tuple[Path, Path]:
    if not psd.is_file(): raise ValueError("Selecione um PSD válido.")
    jpg, pdf = psd.with_suffix(".jpg"), psd.with_suffix(".pdf")
    jsx = f'''#target photoshop
app.displayDialogs = DialogModes.NO;
var doc = app.open(new File({json.dumps(str(psd), ensure_ascii=False)}));
var jpgOptions = new JPEGSaveOptions(); jpgOptions.quality = 12;
doc.saveAs(new File({json.dumps(str(jpg), ensure_ascii=False)}), jpgOptions, true, Extension.LOWERCASE);
var pdfOptions = new PDFSaveOptions();
doc.saveAs(new File({json.dumps(str(pdf), ensure_ascii=False)}), pdfOptions, true, Extension.LOWERCASE);
doc.close(SaveOptions.DONOTSAVECHANGES);'''
    jsx_path = Path(tempfile.gettempdir()) / f"neiva_encarte_exportar_{uuid.uuid4().hex}.jsx"
    jsx_path.write_text(jsx, encoding="utf-8-sig")
    try:
        legacy.run_photoshop_script(legacy.find_photoshop(), jsx_path)
    except Exception:
        jpg.unlink(missing_ok=True)
        pdf.unlink(missing_ok=True)
        raise
    finally:
        jsx_path.unlink(missing_ok=True)
    if not jpg.is_file() or not pdf.is_file():
        jpg.unlink(missing_ok=True)
        pdf.unlink(missing_ok=True)
        raise RuntimeError("O Photoshop não criou o JPG e o PDF.")
    return jpg, pdf
