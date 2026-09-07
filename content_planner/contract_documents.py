"""Modelos, preenchimento local e PDF de contratos com ReportLab."""
import html
import re
import uuid
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether

from .client_management import format_money, format_date_br

REVIEW_NOTICE = 'Revise o contrato antes de utilizá-lo. O conteúdo gerado por IA não substitui orientação jurídica profissional.'
TEMPLATE_NAMES = ['Prestação de serviços','Design gráfico','Social Media','Desenvolvimento de site/software','Edição de vídeo','Serviço recorrente','Modelo personalizado']
BASE_TEMPLATE = '''CONTRATANTE: {{cliente_nome}}, documento {{cliente_documento}}, endereço {{cliente_endereco}}.
PRESTADOR: {{prestador_nome}}, documento {{prestador_documento}}.

1. OBJETO E ESCOPO
Serviço: {{servico_nome}}.
{{servico_descricao}}

2. VALOR E PAGAMENTO
Valor: {{servico_valor}}. Forma de pagamento: {{forma_pagamento}}.

3. PRAZO
Início: {{data_inicio}}. Término: {{data_fim}}.

4. ENTREGAS E ALTERAÇÕES
[Definir entregas, aprovações, quantidade de revisões e responsabilidades das partes.]

5. CANCELAMENTO
[Definir condições de cancelamento e tratamento dos serviços já executados.]

6. CONDIÇÕES ADICIONAIS
[Revisar confidencialidade, uso dos materiais e demais condições aplicáveis ao serviço.]
'''


def variables(client, provider, service=None, contract=None):
    service, contract = service or {}, contract or {}
    return dict(cliente_nome=client.name,cliente_documento=client.document,cliente_endereco=client.address,
                prestador_nome=provider.get('name',''),prestador_documento=provider.get('document',''),
                servico_nome=service.get('name',contract.get('title','')),servico_descricao=service.get('scope') or service.get('description') or contract.get('description',''),
                servico_valor=format_money(contract.get('value_cents',service.get('value_cents',0))),
                forma_pagamento=contract.get('payment_method') or service.get('billing',''),
                data_inicio=format_date_br(contract.get('start_date',service.get('start_date',''))),
                data_fim=format_date_br(contract.get('end_date',service.get('end_date',''))))


def fill_template(content, values):
    # Uma única passagem: conteúdo de campos nunca é avaliado como código/template.
    return re.sub(r'\{\{([a-z_]+)\}\}', lambda m: str(values.get(m[1]) or m[0]), content)


def generate_pdf(document, output_dir):
    content = document.get('content','').strip()
    if not content:
        raise ValueError('Preencha o conteúdo antes de gerar o PDF.')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    target = output_dir / f"contrato_{document['id']}_v{document.get('revision',0)}_{uuid.uuid4().hex[:12]}.pdf"
    temp = target.with_suffix('.tmp')
    styles = getSampleStyleSheet()
    styles['Normal'].fontSize = 10
    styles['Normal'].leading = 15
    styles['Normal'].splitLongWords = True
    styles['Title'].textColor = colors.HexColor('#6C5CE7')
    story = [Paragraph(html.escape(document['title']),styles['Title']),
             Paragraph(f"Situação documental: {html.escape(document.get('document_status','Rascunho'))} | Versão {document.get('revision',0)}",styles['Normal']),Spacer(1,14)]
    if document.get('document_status','Rascunho') == 'Rascunho':
        story.extend([Paragraph(html.escape(REVIEW_NOTICE),styles['Normal']),Spacer(1,14)])
    parties = document.get('parties',{})
    if parties:
        for label, keys in [('Contratante',('cliente_nome','cliente_documento','cliente_endereco')),
                            ('Prestador',('prestador_nome','prestador_documento'))]:
            identification = ' | '.join(str(parties.get(key) or 'Não informado') for key in keys)
            story.append(Paragraph(html.escape(label+': '+identification),styles['Normal']))
        summary = f"Valor: {format_money(document.get('value_cents',0))} | Cobrança: {document.get('billing','Mensal')} | Pagamento: {document.get('payment_method') or 'A definir'}"
        story.append(Paragraph(html.escape(summary),styles['Normal']))
        story.append(Paragraph(html.escape(f"Início: {format_date_br(document.get('start_date',''))} | Término: {format_date_br(document.get('end_date',''))}"),styles['Normal']))
        story.append(Spacer(1,14))
    for line in content.splitlines():
        heading = bool(re.match(r'^\d+[.)]\s',line.strip())) and line.strip().isupper() and len(line)<200
        story.append(Paragraph(html.escape(line) or ' ',styles['Heading2'] if heading else styles['Normal']))
        if not heading:
            story.append(Spacer(1,5))
    story.append(KeepTogether([Spacer(1,24),Paragraph('______________________________<br/>Contratante',styles['Normal']),
                              Spacer(1,24),Paragraph('______________________________<br/>Prestador',styles['Normal'])]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#6E6E7A'))
        canvas.drawString(48,26,f"Gerado em {datetime.now():%d/%m/%Y %H:%M} - Vydra")
        canvas.drawRightString(A4[0]-48,26,f'Página {doc.page}')
        canvas.restoreState()
    try:
        SimpleDocTemplate(str(temp),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=48,bottomMargin=48).build(story,onFirstPage=footer,onLaterPages=footer)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return target
