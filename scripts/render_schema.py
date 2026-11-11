"""Render the final relational schema as an SVG from the checked-in DDL."""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ddl = (ROOT / 'schema.sql').read_text(encoding='utf-8')
    definitions = dict(re.findall(r'CREATE TABLE (\w+) \((.*?)\n\);', ddl, re.S))
    order = ['Departments', 'Doctors', 'Doctor_Schedules', 'Patients', 'Medicines',
             'Medical_Records', 'Appointments', 'Prescriptions', 'Prescription_Items', 'Invoices']
    positions = {name: (40 + index % 5 * 390, 110 if index < 5 else 670) for index, name in enumerate(order)}
    fields = {}
    foreign_keys = []
    for name, definition in definitions.items():
        fields[name] = re.findall(r'^\s+(\w+)\s+((?:SERIAL|INT|VARCHAR\([^)]*\)|NUMERIC\([^)]*\)|TIMESTAMPTZ|TIME|DATE|TEXT|BOOLEAN))([^\n]*)', definition, re.M)
        foreign_keys.extend((name, column, parent) for column, parent in re.findall(
            r'FOREIGN KEY \((\w+)\)\s+REFERENCES (\w+)', definition))
    width, height = 2020, 1250
    shapes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="#f8fafc"/>',
              '<style>text{font-family:Segoe UI,Arial,sans-serif}.title{font-size:26px;font-weight:600;fill:#1a3c6e}.small{font-size:13px;fill:#718596}.table{font-size:17px;font-weight:700;fill:white}.column{font-family:Consolas,monospace;font-size:13px;fill:#405a70}.key{fill:#087f76;font-weight:700}</style>',
              '<text x="40" y="45" class="title">MedConnect | Final Relational Schema</text>',
              '<text x="40" y="72" class="small">10 tables · 14 foreign keys · PK = primary key · FK = foreign key · ? = nullable · source: schema.sql</text>']
    colors = ['#89a5c5', '#7eb4a8', '#b0a0ca', '#c4ac89']
    for index, (child, column, parent) in enumerate(foreign_keys):
        cx, cy = positions[child]
        px, py = positions[parent]
        child_height = 52 + len(fields[child]) * 25
        parent_height = 52 + len(fields[parent]) * 25
        if cy > py:
            source = (cx + 145 + index % 3 * 18, cy)
            target = (px + 145 + index % 3 * 18, py + parent_height)
            lane = 510 + index * 7
        else:
            source = (cx + 150, cy + child_height)
            target = (px + 185, py + parent_height)
            lane = 1100 + index * 8 if cy == 670 else 510 + index * 7
        shapes.append(f'<path d="M{source[0]} {source[1]} V{lane} H{target[0]} V{target[1]}" fill="none" stroke="{colors[index % 4]}" stroke-width="1.6" opacity=".72"/>')
    for name in order:
        x, y = positions[name]
        table_height = 52 + len(fields[name]) * 25
        shapes.extend([f'<rect x="{x}" y="{y}" width="350" height="{table_height}" rx="7" fill="white" stroke="#b6c9d9"/>',
                       f'<path d="M{x+7} {y} H{x+343} Q{x+350} {y} {x+350} {y+7} V{y+40} H{x} V{y+7} Q{x} {y} {x+7} {y}" fill="#214766"/>',
                       f'<text x="{x+14}" y="{y+26}" class="table">{name}</text>'])
        fk_columns = {column for child, column, parent in foreign_keys if child == name}
        for index, (column, data_type, suffix) in enumerate(fields[name]):
            marker = 'PK' if 'PRIMARY KEY' in suffix else 'FK' if column in fk_columns else ''
            nullable = '' if 'NOT NULL' in suffix or marker == 'PK' else '?'
            label = html.escape(column + nullable)
            shapes.append(f'<text x="{x+14}" y="{y+62+index*25}" class="column"><tspan class="key">{marker:2}</tspan> {label}</text>')
            shapes.append(f'<text x="{x+253}" y="{y+62+index*25}" class="small">{html.escape(data_type.replace("VARCHAR", "VCHR"))}</text>')
    shapes.extend(['<text x="40" y="1230" class="small">Foreign-key endpoints connect dependent tables to referenced parents. Unique constraints, participation, retention rules, and normalization decisions are detailed in docs/database_design.md.</text>', '</svg>'])
    target = ROOT / 'docs/diagrams/final_relational_schema.svg'
    target.parent.mkdir(parents=True, exist_ok=True)
    drawing = '\n'.join(shapes)
    attributes = {
        'title': 'font-family="Arial,sans-serif" font-size="26" font-weight="600" fill="#1a3c6e"',
        'small': 'font-family="Arial,sans-serif" font-size="13" fill="#718596"',
        'table': 'font-family="Arial,sans-serif" font-size="17" font-weight="700" fill="white"',
        'column': 'font-family="Courier New,monospace" font-size="13" fill="#405a70"',
        'key': 'fill="#087f76" font-weight="700"',
    }
    for class_name, value in attributes.items():
        drawing = drawing.replace(f'class="{class_name}"', value)
    target.write_text(drawing, encoding='utf-8')
    print(f'Rendered {len(fields)} tables and {len(foreign_keys)} foreign keys to {target.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
