#!/usr/bin/env python3
"""Generate DOCX with Word-native OMML equation objects from Markdown LaTeX.

This helper is intentionally small and deterministic for patent disclosures:
- Markdown output keeps the original LaTeX source unchanged.
- DOCX output uses md_to_docx.py for normal content and images.
- LaTeX spans are temporarily replaced with placeholders, then placeholders are
  replaced in word/document.xml by OMML equation objects.

It supports the disclosure style used by this skill: inline ``\\(...\\)`` and
block ``\\[...\\]`` equations. The OMML text uses Word's linear equation input
where possible, avoiding visible backslash source code and avoiding formula PNGs.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def latex_to_word_linear(latex: str) -> str:
    """Convert a small, patent-friendly LaTeX subset to Word linear math text."""
    s = latex.strip()
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\,", " ")
    s = s.replace("\\ldots", "…")
    s = s.replace("\\geq", "≥").replace("\\leq", "≤")
    s = s.replace("\\min", "min").replace("\\max", "max")
    s = s.replace("\\theta", "θ")
    s = re.sub(r"\\mathrm\{([^{}]+)\}", r"\1", s)
    s = re.sub(r"_\{([^{}]+)\}", r"_\1", s)
    s = re.sub(r"\\tag\{([^{}]+)\}", r"  (\1)", s)
    s = s.replace("\\", "")
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def make_omath(text: str) -> etree._Element:
    omath = etree.Element(f"{{{M_NS}}}oMath")
    mr = etree.SubElement(omath, f"{{{M_NS}}}r")
    mt = etree.SubElement(mr, f"{{{M_NS}}}t")
    mt.text = text
    return omath


def make_text_run(text: str) -> etree._Element:
    wr = etree.Element(f"{{{W_NS}}}r")
    wt = etree.SubElement(wr, f"{{{W_NS}}}t")
    if text.startswith(" ") or text.endswith(" "):
        wt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    wt.text = text
    return wr


def replace_placeholders(docx_in: Path, docx_out: Path, eq_map: dict[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        with zipfile.ZipFile(docx_in) as zin:
            zin.extractall(tmpdir)

        document = tmpdir / "word" / "document.xml"
        parser = etree.XMLParser(remove_blank_text=False)
        tree = etree.parse(str(document), parser)
        root = tree.getroot()

        for text_node in list(root.xpath(".//w:t", namespaces={"w": W_NS})):
            if not text_node.text or "[[EQ" not in text_node.text:
                continue
            parts = re.split(r"(\[\[EQ\d{4}\]\])", text_node.text)
            run = text_node.getparent()
            parent = run.getparent()
            idx = parent.index(run)
            parent.remove(run)
            for offset, part in enumerate(p for p in parts if p):
                parent.insert(idx + offset, make_omath(eq_map[part]) if part in eq_map else make_text_run(part))

        tree.write(str(document), encoding="UTF-8", xml_declaration=True, standalone=True)

        with zipfile.ZipFile(docx_out, "w", zipfile.ZIP_DEFLATED) as zout:
            for path in tmpdir.rglob("*"):
                if path.is_file():
                    zout.write(path, path.relative_to(tmpdir).as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description="Markdown + LaTeX → DOCX with OMML equations")
    parser.add_argument("-i", "--input", required=True, type=Path, help="input Markdown")
    parser.add_argument("-m", "--markdown-output", type=Path, help="copy original Markdown here")
    parser.add_argument("-o", "--output", required=True, type=Path, help="output DOCX")
    parser.add_argument("--base-dir", type=Path, help="image base dir for md_to_docx")
    parser.add_argument("--image-max-width-inches", default="6.2")
    parser.add_argument("--image-max-height-inches", default="8.8")
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.write_text(text, encoding="utf-8")

    eq_map: dict[str, str] = {}
    counter = 1

    def put_equation(match: re.Match[str]) -> str:
        nonlocal counter
        key = f"[[EQ{counter:04d}]]"
        counter += 1
        eq_map[key] = latex_to_word_linear(match.group(1))
        return key

    placeholder_text = re.sub(r"\\\[(.*?)\\\]", put_equation, text, flags=re.S)
    placeholder_text = re.sub(r"\\\((.*?)\\\)", put_equation, placeholder_text, flags=re.S)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        temp_md = tmpdir / "equation_placeholders.md"
        temp_docx = tmpdir / "equation_placeholders.docx"
        temp_md.write_text(placeholder_text, encoding="utf-8")

        cmd = [
            sys.executable,
            str(Path(__file__).with_name("md_to_docx.py")),
            "--input",
            str(temp_md),
            "--output",
            str(temp_docx),
            "--image-max-width-inches",
            str(args.image_max_width_inches),
            "--image-max-height-inches",
            str(args.image_max_height_inches),
            "--no-math-render",
        ]
        if args.base_dir:
            cmd.extend(["--base-dir", str(args.base_dir)])
        subprocess.run(cmd, check=True)
        replace_placeholders(temp_docx, args.output, eq_map)

    print(f"已写入 Word 原生公式版: {args.output}")


if __name__ == "__main__":
    main()
