# Documents

{mod}`macos.document` converts documents between Word, RTF, HTML,
OpenDocument, plain text and PDF, and reads their text. No Word or LibreOffice
needed: it uses the text system of macOS, the one TextEdit uses.

```python
import macos

macos.document.convert("report.docx", "report.pdf")
macos.document.convert("page.html", "page.docx")
macos.document.text("contract.docx")   # 'CONTRACT\nThe parties...'
```

## Converting

{func}`~macos.document.convert` picks the format from the output's extension:

| Reads | Writes |
|---|---|
| `.docx`, `.doc`, `.rtf`, `.rtfd`, `.html`, `.odt`, `.webarchive`, `.txt` | `.pdf`, `.docx`, `.doc`, `.rtf`, `.html`, `.odt`, `.webarchive`, `.txt` |

A PDF is laid out on pages as TextEdit prints them: on `paper` (`'a4'`,
`'letter'` or `'legal'`; by default the one of your region) with a `margin`
in points from each edge (72, an inch, by default).

```python
from pathlib import Path

for doc in Path("~/Contracts").expanduser().glob("*.docx"):
    macos.document.convert(doc, doc.with_suffix(".pdf"), paper="a4", margin=54)
```

What TextEdit keeps survives: fonts, bold and italics, colours, lists, tables
and links. The page layout of a Word document doesn't (columns, headers and
footers, text boxes), so a converted PDF looks like the document opened in
TextEdit, not in Word. Tables are lost when writing Word files (`.docx`,
`.doc`): their cells become lines; they're kept in the other formats.

An HTML page's pictures on the web may be downloaded while it's read.

## Reading the text

{func}`~macos.document.text` returns a document's text, for searching,
indexing or feeding to a model:

```python
text = macos.document.text("minutes.docx")
macos.language.detect(text)   # 'pt'
```

For a PDF, see {func}`macos.pdf.text`.

## Reference

- {func}`macos.document.convert`
- {func}`macos.document.text`
