import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Callable

from . import encarte_legacy as legacy


ProgressCallback = Callable[[int, str], None]


class PhotoExtractor:
    """Extrai as camadas dos grupos GRUPOxx e usa os textos dos BOXes como nomes."""

    def __init__(self, logger: logging.Logger, progress: ProgressCallback) -> None:
        self.logger = logger
        self.progress = progress

    def extract(self, psd: Path, photos_dir: Path) -> list[Path]:
        if not psd.is_file():
            raise FileNotFoundError(f"PSD não encontrado: {psd}")
        photos_dir.mkdir(parents=True, exist_ok=True)
        report = Path(tempfile.gettempdir()) / "encarte_fotos_extraidas.txt"
        report.unlink(missing_ok=True)
        script = self._build_script(psd, photos_dir, report)
        jsx_path = Path(tempfile.gettempdir()) / "encarte_extrair_fotos.jsx"
        jsx_path.write_text(script, encoding="utf-8-sig")

        self.progress(25, "Abrindo o PSD no Photoshop...")
        legacy.run_photoshop_script(legacy.find_photoshop(), jsx_path)
        deadline = time.monotonic() + 180
        lines: list[str] = []
        while time.monotonic() < deadline:
            if report.is_file():
                try:
                    lines = report.read_text(encoding="utf-8-sig").splitlines()
                except (OSError, UnicodeError):
                    lines = []
                if any(line.startswith("DONE|") for line in lines):
                    break
            time.sleep(0.25)
        if not lines or not any(line.startswith("DONE|") for line in lines):
            raise RuntimeError("O Photoshop terminou sem gerar o relatório da extração.")
        exported = [photos_dir / line.split("|", 2)[2] for line in lines if line.startswith("OK|")]
        warnings = [line.split("|", 1)[1] for line in lines if line.startswith("WARN|")]
        if not exported:
            detail = f" Detalhes: {'; '.join(warnings)}" if warnings else ""
            raise RuntimeError(f"Nenhuma imagem foi encontrada em grupos GRUPO01, GRUPO02 etc.{detail}")
        missing = [path.name for path in exported if not path.is_file()]
        if missing:
            raise RuntimeError(f"Algumas imagens não foram criadas: {', '.join(missing)}")
        for warning in warnings:
            self.logger.warning(warning)
        self.logger.info("%d fotos extraídas de %s para %s", len(exported), psd, photos_dir)
        self.progress(100, f"{len(exported)} fotos extraídas e renomeadas.")
        return exported

    @staticmethod
    def _build_script(psd: Path, photos_dir: Path, report: Path) -> str:
        source = json.dumps(str(psd), ensure_ascii=False)
        destination = json.dumps(str(photos_dir), ensure_ascii=False)
        report_path = json.dumps(str(report), ensure_ascii=False)
        return rf'''#target photoshop
app.displayDialogs = DialogModes.NO;
var sourceFile = new File({source});
var outputDir = new Folder({destination});
var reportFile = new File({report_path});
var doc = app.open(sourceFile);
var exportedCount = 0;
var groupCount = 0;

function px(value) {{ return value.as("px"); }}
function center(layer) {{
  var b = layer.bounds;
  return {{ x: (px(b[0]) + px(b[2])) / 2, y: (px(b[1]) + px(b[3])) / 2 }};
}}
function cleanName(value) {{
  value = String(value || "").replace(/[\\\/:*?"<>|]/g, " ");
  value = value.replace(/[\r\n]+/g, " ").replace(/\s+/g, " ");
  value = value.replace(/^\s+|\s+$/g, "").replace(/[. ]+$/g, "");
  return value;
}}
function descriptionIn(container) {{
  for (var i = 0; i < container.layers.length; i++) {{
    var layer = container.layers[i];
    if (layer.typename === "ArtLayer" && /DESCRI/i.test(layer.name)) {{
      var point = center(layer);
      var text = "";
      try {{
        if (layer.kind === LayerKind.TEXT) text = cleanName(layer.textItem.contents);
      }} catch (e) {{}}
      return {{ text: text, x: point.x, y: point.y }};
    }}
    if (layer.typename === "LayerSet") {{
      var nested = descriptionIn(layer);
      if (nested) return nested;
    }}
  }}
  return null;
}}
function collectBoxes(container) {{
  var boxes = [];
  for (var i = 0; i < container.layers.length; i++) {{
    var layer = container.layers[i];
    if (layer.typename === "LayerSet" && /^BOX[_ -]?\d+/i.test(layer.name)) {{
      var description = descriptionIn(layer);
      if (description) {{
        boxes.push({{ layer: layer, description: description.text, x: description.x, y: description.y, used: false }});
      }} else {{
        var point = center(layer);
        boxes.push({{ layer: layer, description: "", x: point.x, y: point.y, used: false }});
      }}
    }}
  }}
  return boxes;
}}
function uniqueFileName(baseName, reserved) {{
  var name = baseName || "Produto sem nome";
  var candidate = name + ".png";
  var number = 2;
  while (reserved[candidate.toLowerCase()]) {{
    candidate = name + " (" + number + ").png";
    number++;
  }}
  reserved[candidate.toLowerCase()] = true;
  return candidate;
}}
function exportGroup(group, parent) {{
  groupCount++;
  var boxes = collectBoxes(parent);
  var images = [];
  for (var i = 0; i < group.layers.length; i++) {{
    var layer = group.layers[i];
    if (layer.typename === "ArtLayer") {{
      var point = center(layer);
      images.push({{ layer: layer, x: point.x, y: point.y, box: null }});
    }}
  }}
  var pairs = [];
  for (var a = 0; a < images.length; a++) {{
    for (var b = 0; b < boxes.length; b++) {{
      var dx = images[a].x - boxes[b].x;
      var dy = images[a].y - boxes[b].y;
      pairs.push({{ image: a, box: b, distance: dx * dx + dy * dy }});
    }}
  }}
  pairs.sort(function(left, right) {{ return left.distance - right.distance; }});
  var assignedImages = {{}};
  for (var p = 0; p < pairs.length; p++) {{
    var pair = pairs[p];
    if (!assignedImages[pair.image] && !boxes[pair.box].used) {{
      images[pair.image].box = boxes[pair.box];
      assignedImages[pair.image] = true;
      boxes[pair.box].used = true;
    }}
  }}
  var reserved = {{}};
  for (var j = 0; j < images.length; j++) {{
    var item = images[j];
    var baseName = item.box && item.box.description ? item.box.description : "";
    if (!baseName && item.box) {{
      baseName = "Produto " + item.box.layer.name;
      reportFile.writeln("WARN|A descrição de " + item.box.layer.name + " não é uma camada de texto; foi usado um nome provisório.");
    }}
    if (!baseName) baseName = cleanName(item.layer.name);
    if (!baseName || /^Camada( |$)/i.test(baseName)) baseName = group.name + " imagem " + (j + 1);
    var fileName = uniqueFileName(baseName, reserved);
    var temp = app.documents.add(doc.width, doc.height, doc.resolution, "temp", NewDocumentMode.RGB, DocumentFill.TRANSPARENT);
    app.activeDocument = doc;
    item.layer.duplicate(temp, ElementPlacement.PLACEATBEGINNING);
    app.activeDocument = temp;
    temp.trim(TrimType.TRANSPARENT, true, true, true, true);
    var options = new PNGSaveOptions();
    options.interlaced = false;
    temp.saveAs(new File(outputDir.fsName + "/" + fileName), options, true, Extension.LOWERCASE);
    temp.close(SaveOptions.DONOTSAVECHANGES);
    reportFile.writeln("OK|" + group.name + "|" + fileName);
    exportedCount++;
  }}
  if (!boxes.length) reportFile.writeln("WARN|Nenhuma descrição de produto foi encontrada perto de " + group.name + ".");
}}
function walk(container) {{
  for (var i = 0; i < container.layers.length; i++) {{
    var layer = container.layers[i];
    if (layer.typename === "LayerSet") {{
      if (/^GRUPO[_ -]?\d+$/i.test(layer.name)) exportGroup(layer, container);
      else walk(layer);
    }}
  }}
}}

reportFile.encoding = "UTF8";
reportFile.open("w");
walk(doc);
if (!groupCount) reportFile.writeln("WARN|O PSD não possui grupos chamados GRUPO01, GRUPO02 etc.");
reportFile.writeln("DONE|" + exportedCount);
reportFile.close();
doc.close(SaveOptions.DONOTSAVECHANGES);
'''
