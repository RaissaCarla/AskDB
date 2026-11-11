"""Gera a fonte Mermaid e a figura vetorial do DER planejado para a V1.

Requer reportlab. Executar da raiz do relatório:
    python diagramas/gerar_der_sqlite_v1.py
Não cria um banco SQLite nem implementa a persistência da aplicação.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
# Nome, posição, atributos (nome, tipo SQLite, restrição).
ENTITIES = [
    ('PerfilUsuario', (20, 650), [
        ('id', 'TEXT', 'PK'), ('nome', 'TEXT', ''),
        ('idioma', 'TEXT', ''), ('preferencias_json', 'TEXT', ''),
    ]),
    ('PerfilLLM', (320, 650), [
        ('id', 'TEXT', 'PK'), ('usuario_id', 'TEXT', 'FK'),
        ('rotulo', 'TEXT', ''), ('provedor', 'TEXT', ''),
        ('endpoint', 'TEXT', ''), ('modelo', 'TEXT', ''),
        ('segredo_ref', 'TEXT', 'opcional'),
    ]),
    ('Conexao', (20, 385), [
        ('id', 'TEXT', 'PK'), ('usuario_id', 'TEXT', 'FK'),
        ('rotulo', 'TEXT', ''), ('host', 'TEXT', ''),
        ('porta', 'INTEGER', ''), ('banco', 'TEXT', ''),
        ('usuario_pg', 'TEXT', ''), ('senha_ref', 'TEXT', 'opcional'),
        ('contexto_path', 'TEXT', ''),
    ]),
    ('Conversa', (320, 385), [
        ('id', 'TEXT', 'PK'), ('conexao_id', 'TEXT', 'FK'),
        ('perfil_llm_id', 'TEXT', 'FK'), ('titulo', 'TEXT', ''),
        ('criada_em', 'TEXT', ''),
    ]),
    ('ConsentimentoAmostra', (20, 85), [
        ('id', 'TEXT', 'PK'), ('conexao_id', 'TEXT', 'FK'),
        ('esquema', 'TEXT', ''), ('tabela', 'TEXT', ''),
        ('autoriza_amostra', 'INTEGER', '0/1'),
        ('autoriza_envio_remoto', 'INTEGER', '0/1'),
        ('atualizado_em', 'TEXT', ''),
    ]),
    ('Mensagem', (320, 85), [
        ('id', 'TEXT', 'PK'), ('conversa_id', 'TEXT', 'FK'),
        ('sequencia', 'INTEGER', ''), ('papel', 'TEXT', ''),
        ('conteudo', 'TEXT', ''), ('sql_proposta', 'TEXT', 'opcional'),
        ('estado_validacao', 'TEXT', 'opcional'), ('criada_em', 'TEXT', ''),
    ]),
]
RELATIONS = [
    ('PerfilUsuario', 'Conexao', 'configura'),
    ('PerfilUsuario', 'PerfilLLM', 'configura'),
    ('Conexao', 'Conversa', 'isola'),
    ('PerfilLLM', 'Conversa', 'orienta'),
    ('Conexao', 'ConsentimentoAmostra', 'delimita'),
    ('Conversa', 'Mensagem', 'contem'),
]
WIDTH, ROW = 240, 17


def height(fields):
    return 31 + ROW * len(fields)


def generate_mermaid():
    lines = ['%% Modelo proposto para a V1; não representa banco implementado.',
             'erDiagram', '    direction TB']
    for parent, child, label in RELATIONS:
        lines.append(f'    {parent} ||--o{{ {child} : {label}')
    for name, _, fields in ENTITIES:
        lines.append(f'    {name} {{')
        for field, kind, constraint in fields:
            suffix = f' {constraint}' if constraint in ('PK', 'FK') else ''
            if constraint and not suffix:
                suffix = f' "{constraint}"'
            lines.append(f'        {kind} {field}{suffix}')
        lines.append('    }')
    target = ROOT / 'diagramas/der_sqlite_v1.mmd'
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def generate_pdf():
    target = ROOT / 'imagens/der_sqlite_v1.pdf'
    pdf = canvas.Canvas(str(target), pagesize=(580, 840))
    pdf.setTitle('AskDB - DER proposto para SQLite local da V1')
    pdf.setAuthor('Autores do projeto AskDB')
    pdf.setFillColor(colors.HexColor('#26334D'))
    pdf.setFont('Helvetica-Bold', 15)
    pdf.drawString(20, 817, 'AskDB | Persistência local da V1')
    pdf.setFont('Helvetica', 9)
    pdf.drawString(20, 801, 'Modelo proposto - configurações, consentimentos e histórico')
    boxes = {}
    for name, (x, y), fields in ENTITIES:
        h = height(fields)
        boxes[name] = (x, y, WIDTH, h)
        pdf.setFillColor(colors.HexColor('#F8FAFD'))
        pdf.setStrokeColor(colors.HexColor('#526480'))
        pdf.roundRect(x, y, WIDTH, h, 5, fill=1, stroke=1)
        pdf.setFillColor(colors.HexColor('#E4EAF5'))
        pdf.rect(x + 1, y + h - 26, WIDTH - 2, 25, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor('#26334D'))
        pdf.setFont('Helvetica-Bold', 11)
        pdf.drawString(x + 10, y + h - 17, name)
        for index, (field, kind, constraint) in enumerate(fields):
            baseline = y + h - 42 - ROW * index
            pdf.setFont('Helvetica', 9)
            pdf.drawString(x + 10, baseline, field)
            pdf.setFont('Helvetica', 8)
            pdf.drawString(x + 151, baseline, kind)
            pdf.drawRightString(x + WIDTH - 9, baseline, constraint)

    def edge(points, start_label, end_label, relation, label_pos):
        pdf.setLineWidth(1)
        pdf.setStrokeColor(colors.HexColor('#526480'))
        path = pdf.beginPath()
        path.moveTo(*points[0])
        for point in points[1:]:
            path.lineTo(*point)
        pdf.drawPath(path)
        pdf.setFillColor(colors.HexColor('#26334D'))
        pdf.setFont('Helvetica', 9)
        pdf.drawString(*start_label, '1')
        pdf.drawString(*end_label, '0..N')
        pdf.setFont('Helvetica-Oblique', 8)
        pdf.drawString(*label_pos, relation)

    edge([(260, 716), (320, 716)], (268, 723), (293, 723), 'configura', (269, 703))
    edge([(140, 650), (140, 569)], (147, 636), (147, 579), 'configura', (148, 609))
    edge([(440, 650), (440, 501)], (447, 635), (447, 511), 'orienta', (448, 581))
    edge([(260, 445), (320, 445)], (268, 452), (293, 452), 'isola', (275, 432))
    edge([(140, 385), (140, 235)], (147, 370), (147, 245), 'delimita', (148, 309))
    edge([(440, 385), (440, 252)], (447, 370), (447, 262), 'contém', (448, 309))
    pdf.setFont('Helvetica', 8)
    notes = [
        'PK: chave primária | FK: chave estrangeira | 0..N: nenhum ou vários registros.',
        'IDs e datas em TEXT; valores booleanos em INTEGER (0/1). Referências a segredos são opcionais.',
        'Contexto de negócio em Markdown. Segredos protegidos por safeStorage/DPAPI, fora das tabelas.',
        'Sem resultados, amostras, catálogo relacional completo ou credenciais em texto puro.',
    ]
    for index, note in enumerate(notes):
        pdf.drawString(20, 63 - 12 * index, note)
    pdf.showPage()
    pdf.save()


if __name__ == '__main__':
    generate_mermaid()
    generate_pdf()
    print('DER Mermaid e PDF gerados.')
