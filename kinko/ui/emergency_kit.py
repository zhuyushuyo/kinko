"""Emergency kit PDF: the recovery key plus where the vault is, for printing and keeping on paper."""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QMarginsF
from PyQt6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument

from .. import __version__
from ..i18n import tr
from . import theme


def build_html(vault_name: str, vault_path: str, vault_id: str, recovery_key: str) -> str:
    e = html.escape
    groups = recovery_key.split("-")
    half = (len(groups) + 1) // 2
    rows = [groups[:half], groups[half:]]
    key_html = "<br>".join("&nbsp;&nbsp;".join(e(g) for g in row) for row in rows if row)
    today = datetime.now().strftime("%Y-%m-%d")
    mono = theme.mono_family()
    h = 'style="font-size:11.5pt; font-weight:700; margin-top:10px; margin-bottom:4px;"'
    return f"""
<html><body style="font-size:10.5pt; color:#23262B;">
<table width="100%" cellspacing="0" cellpadding="0"><tr>
<td><span style="font-size:20pt; font-weight:700; letter-spacing:3px;">KINKO</span><br>
<span style="font-size:13pt; font-weight:700;">{e(tr('kit.title'))}</span></td>
<td align="right" style="color:#5E656F;">{e(tr('kit.created'))}: {today}<br>KINKO {__version__}</td>
</tr></table>
<hr style="border:0; border-top:1px solid #DEE0E2;">
<p>{e(tr('kit.lead'))}</p>
<p {h}>{e(tr('kit.vault'))}</p>
<table cellspacing="0" cellpadding="5" width="100%" style="border:1px solid #DEE0E2;">
<tr><td width="28%" style="color:#5E656F;">{e(tr('kit.vault_name'))}</td><td>{e(vault_name)}</td></tr>
<tr><td style="color:#5E656F;">{e(tr('kit.vault_path'))}</td><td>{e(vault_path)}</td></tr>
<tr><td style="color:#5E656F;">{e(tr('kit.vault_id'))}</td><td style="font-family:'{mono}';">{e(vault_id)}</td></tr>
</table>
<p {h}>{e(tr('kit.recovery_key'))}</p>
<table cellspacing="0" cellpadding="10" width="100%" style="border:2px solid #28457A; background:#E7ECF5;">
<tr><td align="center" style="font-family:'{mono}'; font-size:18pt; font-weight:700; color:#1F3762; line-height:150%;">{key_html}</td></tr>
</table>
<p {h}>{e(tr('kit.master_password'))}</p>
<p style="color:#5E656F;">{e(tr('kit.master_password_note'))}</p>
<table cellspacing="0" cellpadding="12" width="100%" style="border:1px solid #8C929A;"><tr><td>&nbsp;</td></tr></table>
<p {h}>{e(tr('kit.how_title'))}</p>
<ol>
<li>{e(tr('kit.how1'))}</li>
<li>{e(tr('kit.how2'))}</li>
<li>{e(tr('kit.how3'))}</li>
</ol>
<p {h}><span style="color:#9A3C2B;">{e(tr('kit.warn_title'))}</span></p>
<ul>
<li>{e(tr('kit.warn1'))}</li>
<li>{e(tr('kit.warn2'))}</li>
<li>{e(tr('kit.warn3'))}</li>
</ul>
</body></html>"""


def save_pdf(path: str | Path, vault_name: str, vault_path: str, vault_id: str, recovery_key: str) -> Path:
    path = Path(path)
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(16, 12, 16, 12), QPageLayout.Unit.Millimeter)
    writer.setResolution(300)
    writer.setTitle("KINKO " + tr("kit.title"))
    writer.setCreator(f"KINKO {__version__}")
    doc = QTextDocument()
    font = QFont()
    font.setFamilies(theme.ui_families())
    font.setPointSizeF(10)
    doc.setDefaultFont(font)
    doc.setHtml(build_html(vault_name, vault_path, vault_id, recovery_key))
    printer = getattr(doc, "print", None) or getattr(doc, "print_")
    printer(writer)
    return path
