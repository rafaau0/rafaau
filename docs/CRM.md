# CRM local de clientes

## Escopo e compatibilidade

O CRM continua no SQLite da conta selecionada. Não existe sincronização web dos clientes nem API CRUD remota deste módulo. A API remota apenas gera rascunhos, com a sessão/licença existente. O painel administrativo e o Asaas continuam tratando assinantes do aplicativo, não o financeiro dos clientes locais.

O perfil tem Visão Geral, Serviços / Projetos, Contratos, Financeiro e Histórico / Anotações. Cadastro, pesquisa, filtro, planejamento, contratos anteriores e anexos permanecem disponíveis. WhatsApp e tags são complementos do perfil. `Recorrente` conta como cliente ativo; Lead, Inativo e Arquivado não entram na receita mensal.

## Migração e recuperação

`content_planner/crm.py:migrate` executa a migração 1 numa transação `BEGIN IMMEDIATE`, depois da inicialização legada. Não remove tabelas/colunas. Bancos com clientes recebem antes um backup SQLite consistente `*.pre-crm-<uuid>.bak`, na pasta do banco. `crm_migrations` evita repetir a migração. Uma falha deve interromper a inicialização, não continuar com esquema parcial.

Novas tabelas: `crm_profiles`, `crm_services`, `crm_documents`, `crm_contract_versions`, `crm_templates`, `crm_charges`, `crm_receipts`, `crm_notes`, `crm_activities` e `crm_migrations`.

Os contratos continuam na tabela `contracts`; `crm_documents` acrescenta conteúdo e situação documental. IDs de serviço/contrato/cobrança são validados junto ao cliente na camada de dados. O proprietário é determinado pelo arquivo da conta, não por um ID arbitrário do formulário. Isso preserva o isolamento do aplicativo, mas não é criptografia nem proteção contra alguém com acesso direto aos arquivos do Windows.

Para recuperação, feche o aplicativo e preserve uma cópia do banco atual e da pasta `contracts` antes de restaurar um backup. Backups anteriores à migração não contêm as operações posteriores. Não restaurar automaticamente sobre dados atuais.

## Contratos e valores

- Situação comercial legada: Rascunho, Ativo, Encerrado, Cancelado. Continua controlando vigência.
- Situação documental: Rascunho, Enviado, Assinado, Encerrado, Cancelado. “Enviado” e “Assinado” são registros manuais, sem envio ou assinatura eletrônica.
- Documentos finalizados e arquivados não são editados: duplicar cria outro rascunho. Revisões usam controle otimista para recusar edição desatualizada. O histórico conserva conteúdo anterior e dados das partes.
- Arquivamento apenas organiza o documento; encerrar/cancelar altera também a situação comercial. Contratos com cobranças não podem trocar de serviço nem ser excluídos. Clientes com histórico financeiro devem ser arquivados, não excluídos.
- PDFs anexados são copiados para a conta. PDFs gerados ficam em `contracts/<cliente>/generated`, com ID, versão e sufixo único. Substituir um anexo não remove os arquivos das versões anteriores. Esses arquivos e backups podem exigir limpeza manual futura, após revisar retenção.
- Modelos são bases editáveis com campos a completar, não textos juridicamente certificados. Campos não preenchidos continuam visíveis para revisão. Nenhum modelo executa código.
- Receita mensal considera apenas contratos comerciais Ativos, já iniciados e não vencidos, com cobrança Mensal, de clientes Ativos/Recorrentes. Contratos antigos mantêm periodicidade Mensal.
- O valor contratado de referência no perfil soma serviços fora de Orçamento/Cancelado e contratos avulsos fora de Rascunho/Cancelado. Contratos vinculados não são somados novamente. Para mensalidades, representa um mês, não todo o prazo.

## Financeiro e histórico

Cobranças são lançamentos manuais por parcela/competência; não se repetem automaticamente. Recebimentos parciais possuem data real e não podem exceder o saldo. A soma de cobranças não canceladas define o total cobrado. Pendente é cobrado menos recebido; vencido é o saldo com vencimento anterior à data local de hoje. Não há nota fiscal nem conciliação bancária.

Cancelamento de cobrança só é permitido sem recebimentos. Recebimentos são preservados; edição, estorno e conciliação estão fora desta implementação. Operações financeiras usam transação de escrita e identificador idempotente. Eventos são registrados em UTC, com descrições resumidas; notas ficam separadas. O histórico anterior à migração não é inventado.

## IA no servidor

Nova rota: `POST /v1/contracts/draft`, em `ai_service/app/contract_ai.py`, registrada pelo `main.py`. Corpo aceito: `kind`, `scope`, `terms`. Campos adicionais, inclusive IDs de outros usuários, são recusados. A rota usa `current_client`, valida plano e reserva cota por licença/mês em `contract_ai_usage`, independentemente de `monthly_usage` dos cortes. Falha de geração devolve a reserva.

Configuração:

- `OPENAI_API_KEY`: chave já usada no servidor.
- `CONTRACT_AI_MONTHLY_LIMIT`: inteiro, padrão `0` (desabilitado), teto 1000 por licença/mês. Exemplo para validação controlada: `5`.
- `CONTRACT_AI_MODEL`: opcional; usa `OPENAI_MODEL` ou seu padrão existente.

A interface preenche o formulário com o serviço mediante ação do usuário. Identificadores pessoais conhecidos são substituídos por placeholders antes do envio; escopo e condições livres ainda precisam ser revisados pelo usuário para evitar dados sensíveis desnecessários. Dados das partes são preenchidos localmente após a resposta. OpenAI recebe `store:false`, formato estruturado e nenhuma ferramenta. O conteúdo sempre abre como rascunho e só é persistido quando o usuário salva. Não há acesso da IA ao banco local.

O recurso precisa do deploy da API atualizada e das variáveis acima; o build do EXE sozinho não habilita a rota. Geração real e qualidade jurídica exigem validação adicional; testes automatizados usam respostas controladas, não credenciais de produção.

## Verificações

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
$env:CRM_UI_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_crm_ui.py -v
.\.venv\Scripts\python.exe -m compileall -q content_planner ai_service tests
```

O teste gráfico usa banco temporário e plano isolado; exige sessão Tk disponível. `scripts/qa_contract_pdf.py` gera um documento sintético de múltiplas páginas e PNGs em `exports/qa-crm`. Pypdf e pypdfium2 são ferramentas opcionais de QA em `exports/qa-tools`, não dependências do aplicativo.

## Registro da entrega local (2026-09-07)

- 76 testes Python passaram, incluindo o teste gráfico habilitado. Compilação Python e `pip check` passaram.
- Lint, `tsc --noEmit` e build do site passaram, sem mudanças de funcionalidades web.
- PDF sintético de três páginas: extração de texto, renderização e inspeção de todas as páginas realizadas; títulos de cláusulas acompanham o parágrafo seguinte.
- A integração real com OpenAI não foi executada; respostas do provedor foram substituídas somente nos testes. Nenhum deploy remoto ou publicação de release foi realizado nesta etapa.
- Build PyInstaller concluído: `dist/NeivaPlanner_v1.exe`. Conteúdo do executável conferido, incluindo CRM, gerador de contratos, FFmpeg e FFprobe. O teste gráfico foi realizado no código-fonte com banco isolado; ainda é necessária validação do EXE em Windows limpo.

Arquivos novos: `content_planner/crm.py`, `content_planner/crm_view.py`, `content_planner/contract_documents.py`, `ai_service/app/contract_ai.py`, `tests/test_crm.py`, `tests/test_crm_ui.py`, `tests/test_contract_ai.py`, `scripts/qa_contract_pdf.py`, `requirements-test.txt` e este documento.

Arquivos alterados: `content_planner/database.py`, `content_planner/client_management.py`, `content_planner/client_management_view.py`, `content_planner/dashboard_view.py`, `content_planner/ui.py`, `ai_service/app/main.py`, `ai_service/.env.example`, `ai_service/README.md`, `.github/workflows/quality.yml`, `README.md` e `AGENTS.md`. O workflow apenas acrescenta dependências de teste; a exigência de assinatura stable permanece intacta.
