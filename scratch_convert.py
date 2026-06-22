import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

def iter_block_items(parent):
    if isinstance(parent, Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("something's not right")
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

doc = docx.Document(r"D:\vibe\election-data\local\source\Voter_File_Layout.docx")
lines = []
for block in iter_block_items(doc):
    if isinstance(block, Paragraph):
        text = block.text.strip()
        if text:
            if block.style.name.startswith('Heading'):
                level = int(block.style.name.split(' ')[-1]) if block.style.name[-1].isdigit() else 1
                lines.append(f"{'#' * level} {text}")
            else:
                lines.append(text)
    elif isinstance(block, Table):
        lines.append('')
        for i, row in enumerate(block.rows):
            # Replacing newlines to keep table cells on single lines
            row_data = [cell.text.replace('\n', ' ').replace('\r', '').strip() for cell in row.cells]
            lines.append('| ' + ' | '.join(row_data) + ' |')
            if i == 0:
                lines.append('|' + '|'.join(['---'] * len(row_data)) + '|')
        lines.append('')

with open(r"D:\vibe\election-data\local\source\Voter_File_Layout.md", "w", encoding="utf-8") as f:
    f.write('\n'.join(lines))
