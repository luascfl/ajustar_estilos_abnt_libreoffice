#!/usr/bin/env python3
"""
Gera templates do Writer sem precisar abrir o LibreOffice.
- ABNT_Ajustado.ott (Arial)
- ABNT_OrganizeJr.ott (Open Sans / League Spartan / Lexend)
- Redefine/achata os estilos padrões via RESET_PARAGRAPH_STYLES.

Ambos com margens A4 ABNT: topo/esq 3 cm, baixo/dir 2 cm.
"""
import pathlib
import zipfile
from typing import Dict, List

PROFILE = pathlib.Path.home() / ".config" / "libreoffice" / "4" / "user"
STYLE_PREFIX = "ABNT - "

# Estilos nativos que serão achatados. Deixe só o que precisa sobrescrever;
# quanto menor essa lista, menos “ABNT - …” aparecem no Writer.
RESET_PARAGRAPH_STYLES = [
    "Standard",
]


def paragraph_style_xml(name: str, font: str, size_pt: float, weight: str, align: str,
                        margin_left_cm: float, indent_first_cm: float, line_height_pct: int,
                        parent: str = "Standard", display_name: str = None,
                        style_class: str = "text", list_style: str = None) -> str:
    display = display_name or name
    parent_attr = f' style:parent-style-name="{parent}"' if parent else ""
    list_attr = f' text:list-style-name="{list_style}"' if list_style else ""
    return f"""
    <style:style style:name="{name}" style:family="paragraph"{parent_attr} style:display-name="{display}" style:class="{style_class}">
      <style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0cm" fo:margin-left="{margin_left_cm}cm" fo:margin-right="0cm"
          fo:text-indent="{indent_first_cm}cm" fo:text-align="{align}" style:line-height="{line_height_pct}%" {list_attr}/>
      <style:text-properties style:font-name="{font}" fo:font-size="{size_pt}pt" fo:font-family="{font}" fo:font-weight="{weight}"/>
    </style:style>""".strip()


def numbering_list_style_xml(name: str, num_format: str = "1") -> str:
    """List style that produces 1 2 3 numbering with a trailing space."""
    return f"""
    <text:list-style style:name="{name}">
      <text:list-level-style-number text:level="1" style:num-format="{num_format}" style:num-suffix=" " text:start-value="1">
        <style:list-level-properties text:list-level-position-and-space-mode="label-alignment" fo:text-indent="0cm" fo:margin-left="0cm">
          <style:list-level-label-alignment text:label-followed-by="space"/>
        </style:list-level-properties>
      </text:list-level-style-number>
    </text:list-style>""".strip()


def build_styles_xml(spec: Dict) -> bytes:
    fonts = "\n".join(
        f'    <style:font-face style:name="{font}" svg:font-family="{font}"/>'
        for font in spec["fonts"]
    )

    default = spec["default"]
    default_xml = f"""
    <style:default-style style:family="paragraph">
      <style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0cm" fo:margin-left="{default['margin_left']}cm" fo:margin-right="0cm"
          fo:text-indent="{default['indent_first']}cm" style:line-height="{default['line_height']}%" fo:text-align="{default['align']}"/>
      <style:text-properties style:font-name="{default['font']}" fo:font-size="{default['size']}pt" fo:font-family="{default['font']}"/>
    </style:default-style>""".strip()

    merged_paragraphs: Dict[str, Dict] = {}
    list_styles: Dict[str, str] = {}

    def register_style(style_data: Dict):
        """Merge defaults with overrides so we can flatten/alter any style name."""
        name = style_data["name"]
        overrides = {k: v for k, v in style_data.items() if k != "name"}
        display_name = overrides.get("display_name")
        if display_name is None and name != "Standard":
            display_name = f"{STYLE_PREFIX}{name}"
        merged_paragraphs[name] = {**default, **overrides, "display_name": display_name}
        if "list_style" in overrides:
            list_styles[overrides["list_style"]] = numbering_list_style_xml(overrides["list_style"])

    for reset_style in spec.get("reset_paragraphs", []):
        register_style({"name": reset_style} if isinstance(reset_style, str) else reset_style)

    for style in spec.get("paragraphs", []):
        register_style(style)

    list_styles_xml = "\n\n".join(list_styles.values())

    paragraphs = "\n\n".join(
        paragraph_style_xml(
            name,
            st["font"],
            st["size"],
            st["weight"],
            st["align"],
            st["margin_left"],
            st["indent_first"],
            st["line_height"],
            st.get("parent", "Standard"),
            st.get("display_name", name),
            st.get("class", "text"),
            st.get("list_style"),
        )
        for name, st in merged_paragraphs.items()
    )

    page = spec["page"]

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
    xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
    office:version="1.3">
  <office:font-face-decls>
{fonts}
  </office:font-face-decls>
  <office:styles>
{list_styles_xml}

{default_xml}

{paragraphs}
  </office:styles>

  <office:automatic-styles>
    <style:page-layout style:name="pm1">
      <style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" style:print-orientation="portrait"
          fo:margin-top="{page['top']}cm" fo:margin-bottom="{page['bottom']}cm" fo:margin-left="{page['left']}cm" fo:margin-right="{page['right']}cm"
          style:writing-mode="lr-tb" style:layout-grid-mode="none"/>
      <style:header-style/>
      <style:footer-style/>
    </style:page-layout>
  </office:automatic-styles>

  <office:master-styles>
    <style:master-page style:name="Standard" style:page-layout-name="pm1"/>
  </office:master-styles>
</office:document-styles>
""".encode("utf-8")


def build_content_xml(fonts: List[str]) -> bytes:
    font_decls = "\n".join(
        f'    <style:font-face style:name="{font}" svg:font-family="{font}"/>' for font in fonts
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
    xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
    office:version="1.3">
  <office:scripts/>
  <office:font-face-decls>
{font_decls}
  </office:font-face-decls>
  <office:automatic-styles/>
  <office:body>
    <office:text>
      <text:p text:style-name="Standard"/>
    </office:text>
  </office:body>
</office:document-content>
""".encode("utf-8")


def build_common_files(styles_xml: bytes, content_xml: bytes) -> Dict[str, tuple]:
    mimetype = b"application/vnd.oasis.opendocument.text-template"
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text-template"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/>
</manifest:manifest>
""".encode("utf-8")

    meta = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    office:version="1.3">
  <office:meta>
    <meta:generator>Generated by script</meta:generator>
  </office:meta>
</office:document-meta>
""".encode("utf-8")

    settings = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"
    office:version="1.3">
  <office:settings>
    <config:config-item-set config:name="ooo:view-settings"/>
    <config:config-item-set config:name="ooo:configuration-settings"/>
  </office:settings>
</office:document-settings>
""".encode("utf-8")

    return {
        "mimetype": (mimetype, zipfile.ZIP_STORED),
        "META-INF/manifest.xml": (manifest, zipfile.ZIP_DEFLATED),
        "meta.xml": (meta, zipfile.ZIP_DEFLATED),
        "settings.xml": (settings, zipfile.ZIP_DEFLATED),
        "styles.xml": (styles_xml, zipfile.ZIP_DEFLATED),
        "content.xml": (content_xml, zipfile.ZIP_DEFLATED),
    }


def write_template(path: pathlib.Path, spec: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    styles_xml = build_styles_xml(spec)
    content_xml = build_content_xml(spec["fonts"])
    files = build_common_files(styles_xml, content_xml)
    with zipfile.ZipFile(path, "w") as zf:
        data, ctype = files.pop("mimetype")
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = ctype
        zf.writestr(info, data)
        for name, (data, ctype) in files.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = ctype
            zf.writestr(info, data)
    print(f"Template salvo em {path}")


def main():
    abnt_spec = {
        "fonts": ["Arial"],
        "default": {
            "font": "Arial",
            "size": 12,
            "weight": "normal",
            "align": "justify",
            "margin_left": 0,
            "indent_first": 1.25,
            "line_height": 150,
        },
        "reset_paragraphs": RESET_PARAGRAPH_STYLES,
        "paragraphs": [
            {
                "name": "Title",
                "font": "Arial",
                "size": 12,
                "weight": "bold",
                "align": "center",
                "margin_left": 0,
                "indent_first": 0,
                "line_height": 100,
            },
            {
                "name": "Subtitle",
                "font": "Arial",
                "size": 12,
                "weight": "normal",
                "align": "justify",
                "margin_left": 7,
                "indent_first": 7,
                "line_height": 100,
            },
            {
                "name": "Heading 1",
                "font": "Arial",
                "size": 12,
                "weight": "bold",
                "align": "start",
                "margin_left": 0,
                "indent_first": 0,
                "line_height": 150,
                "list_style": "HeadingNumbering",
            },
            {
                "name": "Heading 2",
                "font": "Arial",
                "size": 12,
                "weight": "normal",
                "align": "start",
                "margin_left": 0,
                "indent_first": 0,
                "line_height": 150,
            },
            {
                "name": "ResumoAbstract",
                "font": "Arial",
                "size": 12,
                "weight": "normal",
                "align": "justify",
                "margin_left": 0,
                "indent_first": 0,
                "line_height": 100,
            },
            {
                "name": "Citacao longa",
                "font": "Arial",
                "size": 10,
                "weight": "normal",
                "align": "justify",
                "margin_left": 4,
                "indent_first": 0,
                "line_height": 100,
            },
        ],
        "page": {"top": 3, "bottom": 2, "left": 3, "right": 2},
    }

    org_spec = {
        "fonts": ["Open Sans", "League Spartan", "Lexend"],
        "default": {
            "font": "Open Sans",
            "size": 12,
            "weight": "normal",
            "align": "justify",
            "margin_left": 0,
            "indent_first": 1.25,
            "line_height": 150,
        },
        "reset_paragraphs": RESET_PARAGRAPH_STYLES,
        "paragraphs": [
            {
                "name": "Title",  # Pré-textuais não numeradas
                "font": "League Spartan",
                "size": 12,
                "weight": "bold",
                "align": "center",
                "margin_left": 0,
                "indent_first": 0,
                "line_height": 100,
            },
            {
                "name": "Subtitle",  # Objetivo/autor
                "font": "Open Sans",
                "size": 12,
                "weight": "normal",
                "align": "justify",
                "margin_left": 7,
                "indent_first": 7,
                "line_height": 100,
            },
            {
                "name": "Heading 1",  # Seções numeradas
                "font": "League Spartan",
                "size": 12,
                "weight": "bold",
                "align": "start",
                "margin_left": 0,
                "indent_first": 0,
                "line_height": 150,
                "list_style": "HeadingNumbering",
            },
            {
                "name": "Heading 2",  # Citação longa (Cabeçalho 4)
                "font": "Open Sans",
                "size": 10,
                "weight": "normal",
                "align": "justify",
                "margin_left": 4,
                "indent_first": 4,
                "line_height": 150,
            },
            {
                "name": "Heading 3",  # REFERÊNCIAS título
                "font": "League Spartan",
                "size": 12,
                "weight": "bold",
                "align": "center",
                "margin_left": 0,
                "indent_first": 0,
                "line_height": 150,
            },
        ],
        "page": {"top": 3, "bottom": 2, "left": 3, "right": 2},
    }

    write_template(PROFILE / "template" / "ABNT_Ajustado.ott", abnt_spec)
    write_template(PROFILE / "template" / "ABNT_OrganizeJr.ott", org_spec)


if __name__ == "__main__":
    main()
