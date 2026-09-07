"""Gera e inspeciona um PDF sintético. Ferramentas de QA não são dependências do app."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'exports'/'qa-tools'))

from content_planner.contract_documents import generate_pdf


def main():
    from pypdf import PdfReader
    import pypdfium2 as pdfium
    output=ROOT/'exports'/'qa-crm'
    document=dict(id=1,title='Contrato de prestação de serviços - Revisão',document_status='Rascunho',revision=2,
        parties={'cliente_nome':'Cliente de Teste','cliente_documento':'000.000.000-00','cliente_endereco':'Endereço de Teste','prestador_nome':'Prestador de Teste','prestador_documento':'Não informado'},
        value_cents=123456,billing='Única',payment_method='Duas parcelas',start_date='2026-09-07',end_date='2026-10-07',
        content='CONTRATANTE: Cliente de Teste, documento 000.000.000-00.\nPRESTADOR: Prestador de Teste.\n'
        'Valor: R$ 1.234,56. Início: 07/09/2026. Término: 07/10/2026.\n\n'+
        '\n\n'.join(f'{i}. ESCOPO E CONDIÇÕES\nTexto de teste para verificar acentuação, alinhamento, espaços e continuidade entre páginas. '
                    'Conteúdo com <tags> & caracteres especiais deve aparecer como texto, sem interpretação. '*3 for i in range(1,13)))
    target=generate_pdf(document,output)
    reader=PdfReader(target)
    text='\n'.join(page.extract_text() for page in reader.pages)
    assert 'R$ 1.234,56' in text and '<tags>' in text and '12. ESCOPO' in text
    with pdfium.PdfDocument(str(target)) as pdf:
        for index in range(len(pdf)):
            page=pdf[index]
            bitmap=page.render(scale=1.3)
            bitmap.to_pil().save(output/f'page-{index+1}.png')
            bitmap.close(); page.close()
    print(target)
    print(f'{len(reader.pages)} páginas; texto e renderização conferidos automaticamente.')


if __name__=='__main__':
    main()
