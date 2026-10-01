# Actions: Captura de voz ao arquivo, fatia fina de ponta a ponta

> Identificador: `001-captura-voz-ao-arquivo`
> Data: `2026-08-11`
> Roadmap: `_reversa_forward/001-captura-voz-ao-arquivo/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 60 |
| Paralelizáveis (`[//]`) | 18 |
| Maior cadeia de dependência | 10 (T001 → T004 → T019 → T023 → T025 → T050 → T051 → T052 → T053 → T054) |

🟡 A ordem das fases respeita a ordem de construção do `roadmap.md#8`: configuração e acervo primeiro, transcrição em seguida, classificação depois, e só então a esteira completa, o painel e o digest. A fase de testes vem antes do núcleo porque as garantias mais críticas do produto, escrita atômica e ausência de alteração de estado por carregamento, são difíceis de verificar depois.

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar a estrutura de pacote Python do projeto e o arquivo de dependências, sem lógica de negócio | - | `[//]` | `pyproject.toml` | 🟡 | `[X]` |
| T002 | Escrever `.env.example` com os 39 parâmetros, marcando obrigatórios e padrões conforme as seções 9.1 das specs | - | `[//]` | `.env.example` | 🟡 | `[X]` |
| T003 | Escrever `.gitignore` garantindo que `.env` e a pasta de dados fiquem fora do versionamento | - | `[//]` | `.gitignore` | 🟡 | `[X]` |
| T004 | Implementar a carga do `.env` com tipagem dos valores e os padrões documentados | T001, T002 | - | `memory_card/config.py` | 🟡 | `[X]` |
| T005 | Implementar a validação dos oito parâmetros obrigatórios, falhando na inicialização com erro que nomeia o parâmetro ausente | T004 | - | `memory_card/config.py` | 🟡 | `[X]` |
| T006 | Implementar a recusa de inicialização quando `PAINEL_INTERFACE` não for endereço de loopback | T004 | - | `memory_card/config.py` | 🟡 | `[X]` |
| T007 | Implementar o alerta de divergência entre `PAINEL_URL_BASE` e o par `PAINEL_INTERFACE`/`PAINEL_PORTA` | T004 | - | `memory_card/config.py` | 🟡 | `[X]` |
| T008 | Configurar log estruturado central, com campos comuns e sem registrar segredos nem conteúdo integral | T001 | `[//]` | `memory_card/log.py` | 🟡 | `[X]` |
| T009 | Escrever o arquivo inicial de prompt de classificação, pedindo assunto, tipo e lista de próximos passos | T002 | `[//]` | `config/prompt_classificacao.txt` | 🟡 | `[X]` |
| T010 | Criar automaticamente as pastas de dados ausentes na inicialização, registrando que foram criadas | T004 | - | `memory_card/config.py` | 🟡 | `[X]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T011 | Testar que a ausência de cada parâmetro obrigatório impede a inicialização e nomeia o parâmetro | T005 | `[//]` | `tests/test_config.py` | 🟡 | `[X]` |
| T012 | Testar que interface não-loopback impede a inicialização do painel | T006 | `[//]` | `tests/test_config_rede.py` | 🟡 | `[X]` |
| T013 | Testar que a interrupção durante a gravação de um registro nunca deixa arquivo parcial no acervo | T020 | `[//]` | `tests/test_acervo_atomicidade.py` | 🟡 | `[X]` |
| T014 | Testar que o identificador de um registro permanece o mesmo após o arquivo ser movido ou renomeado | T022 | `[//]` | `tests/test_acervo_id.py` | 🟡 | `[X]` |
| T015 | Testar que a fila retoma pela etapa correta após reinício, sem duplicar registro nem repetir transcrição concluída | T036 | `[//]` | `tests/test_fila.py` | 🟡 | `[X]` |
| T016 | Testar que substituir o adaptador de provedor por uma versão simulada não exige alteração em nenhum outro arquivo | T029 | `[//]` | `tests/test_classificacao_fronteira.py` | 🟡 | `[X]` |
| T017 | Testar que uma requisição de leitura à página de confirmação não altera o estado do registro | T048 | `[//]` | `tests/test_painel_confirmacao.py` | 🟡 | `[X]` |
| T018 | Testar que a seleção do digest retorna os mais antigos primeiro e respeita o limite configurado | T050 | `[//]` | `tests/test_digest_selecao.py` | 🟡 | `[X]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T019 | Definir a entidade `Registro` com todos os campos do `data-delta.md`, incluindo `origem` com valor `reuniao`, `proximos_passos` como lista e `contem_terceiros` | T004 | - | `memory_card/acervo/modelo.py` | 🟡 | `[X]` |
| T020 | Implementar a serialização do `Registro` em markdown com cabeçalho de metadados e escrita atômica por arquivo temporário e renomeação | T019 | - | `memory_card/acervo/escrita.py` | 🟡 | `[X]` |
| T021 | Implementar a derivação automática da pasta de destino a partir da data de captura, com granularidade configurável | T019 | - | `memory_card/acervo/caminhos.py` | 🟡 | `[X]` |
| T022 | Implementar a geração de identificador estável e a normalização do nome de arquivo, com truncamento pelo limite configurado e preservação do assunto íntegro nos metadados | T019 | - | `memory_card/acervo/caminhos.py` | 🟡 | `[X]` |
| T023 | Implementar a leitura de um arquivo markdown do acervo de volta para a entidade `Registro` | T019 | - | `memory_card/acervo/leitura.py` | 🟡 | `[X]` |
| T024 | Implementar a alteração do campo de estado e da data da mudança, preservando todos os demais campos e nunca tocando no texto bruto | T023 | - | `memory_card/acervo/estado.py` | 🟡 | `[X]` |
| T025 | Implementar o índice auxiliar, com construção incremental e reconstrução integral a partir dos arquivos | T023 | - | `memory_card/acervo/indice.py` | 🟡 | `[X]` |
| T026 | Implementar a chamada ao Whisper local com modelo, idioma e dispositivo lidos da configuração | T004 | - | `memory_card/transcricao/whisper_local.py` | 🟡 | `[X]` |
| T027 | Implementar a política de duração, classificando o áudio como curto ou longo e aplicando tempo limite distinto a cada caso | T026 | - | `memory_card/transcricao/politica.py` | 🔴 | `[X]` |
| T028 | Tratar transcrição vazia como resultado válido sinalizado, e arquivo corrompido, formato não suportado e memória insuficiente como erros distintos e nomeados | T026 | - | `memory_card/transcricao/whisper_local.py` | 🟡 | `[X]` |
| T029 | Definir a fronteira única de classificação: contrato de entrada, contrato de saída e seleção do adaptador pela configuração | T004 | - | `memory_card/classificacao/fronteira.py` | 🟡 | `[X]` |
| T030 | Implementar um adaptador concreto de provedor por trás da fronteira, lendo chave, modelo e endereço da configuração, e usando imposição de esquema pelo provedor quando disponível, com o conjunto fechado de tipos declarado como enumeração a partir de `LLM_TIPOS_REGISTRO` | T029 | - | `memory_card/classificacao/adaptador.py` | 🟡 | `[X]` |
| T031 | Implementar a validação da resposta, rejeitando tipo fora do conjunto fechado e campos ausentes, com uma nova tentativa antes de desistir. Permanece obrigatória mesmo com a imposição de esquema do T030 ativa: é a garantia portável para provedores que não oferecem o recurso | T029 | - | `memory_card/classificacao/validacao.py` | 🟡 | `[X]` |
| T032 | Implementar a modalidade de duas passagens para áudio longo, extraindo temas e encaminhamentos por blocos e consolidando em um assunto com lista de próximos passos | T030, T031 | - | `memory_card/classificacao/duas_passagens.py` | 🔴 | `[X]` |
| T033 | Implementar a política de novas tentativas com espera crescente e a distinção entre indisponibilidade, cota esgotada, recusa por filtro de conteúdo e tempo excedido | T030 | - | `memory_card/classificacao/erros.py` | 🟡 | `[X]` |
| T034 | Registrar provedor, modelo, tokens de entrada e saída e custo estimado a cada chamada de classificação | T030 | - | `memory_card/classificacao/custo.py` | 🟡 | `[X]` |
| T035 | Definir a entidade `ItemFila` com o campo de etapa e implementar sua persistência individual em disco | T004 | - | `memory_card/fila/modelo.py` | 🟡 | `[X]` |
| T036 | Implementar a máquina de etapas da fila, permitindo retomar do ponto correto após reinício sem repetir etapa já concluída | T035 | - | `memory_card/fila/maquina.py` | 🟡 | `[X]` |
| T037 | Implementar a execução estritamente serial da fila, garantindo uma transcrição por vez | T036 | - | `memory_card/fila/executor.py` | 🟡 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T038 | Implementar o laço de long polling contra a API do Telegram, com deslocamento de leitura persistido e avanço somente após conclusão do processamento | T004 | - | `memory_card/captura/polling.py` | 🟡 | `[X]` |
| T039 | Implementar o descarte silencioso de mensagens de remetente não autorizado, sem resposta e com registro da tentativa em log | T038 | - | `memory_card/captura/autorizacao.py` | 🟡 | `[X]` |
| T040 | Implementar o download do áudio para disco local, com até três tentativas, espera crescente e erro nomeando a etapa em caso de falha | T038 | - | `memory_card/captura/download.py` | 🟡 | `[X]` |
| T041 | Implementar o envio de aviso de recebimento, confirmação com o assunto atribuído e mensagem de erro identificando a etapa que falhou | T038 | - | `memory_card/captura/respostas.py` | 🟡 | `[X]` |
| T042 | Implementar a captura por texto digitado, tratando o conteúdo como transcrição pronta e pulando a etapa de transcrição | T038 | - | `memory_card/captura/texto.py` | 🟡 | `[X]` |
| T043 | Implementar o aviso de processamento estendido enviado ao receber áudio acima do limite de duração configurado | T027, T041 | - | `memory_card/captura/respostas.py` | 🔴 | `[X]` |
| T044 | Implementar a orquestração da esteira, ligando captura, fila, transcrição, classificação e arquivamento, garantindo que falha de classificação não impeça o arquivamento | T020, T027, T032, T037, T040 | - | `memory_card/esteira.py` | 🟡 | `[X]` |
| T045 | Implementar o servidor HTTP local vinculado exclusivamente a loopback, recusando iniciar em porta ocupada em vez de escolher outra | T006, T007 | - | `memory_card/painel/servidor.py` | 🟡 | `[X]` |
| T046 | Implementar a página inicial do painel com as contagens do período: capturados, arquivados, executados, descartados, pendentes e com falha | T025, T045 | - | `memory_card/painel/visao_periodo.py` | 🟡 | `[X]` |
| T047 | Implementar a página de registro individual, exibindo texto bruto e lista de próximos passos | T023, T045 | - | `memory_card/painel/registro.py` | 🟡 | `[X]` |
| T048 | Implementar a página de confirmação de marcação em duas etapas, com leitura que não altera estado e envio explícito que aplica a mudança de forma idempotente | T024, T045 | - | `memory_card/painel/confirmacao.py` | 🟡 | `[X]` |
| T049 | Implementar os filtros por estado, tipo e período, mais a busca textual simples sobre assunto e texto bruto | T046 | - | `memory_card/painel/filtros.py` | 🟡 | `[X]` |
| T050 | Implementar a seleção dos registros do digest: apenas pendentes, ordenados dos mais antigos primeiro, limitados pela quantidade configurada | T025 | - | `memory_card/digest/selecao.py` | 🟡 | `[X]` |
| T051 | Implementar a montagem do e-mail com assunto, próximos passos, data, marcação de origem, os dois links de confirmação e o total de pendentes, legível com imagens bloqueadas | T045, T050 | - | `memory_card/digest/montagem.py` | 🟡 | `[X]` |
| T052 | Implementar o envio por servidor de saída, com erro distinto para credencial inválida, destinatário rejeitado e indisponibilidade transitória | T051 | - | `memory_card/digest/envio.py` | 🟡 | `[X]` |
| T053 | Implementar o agendador interno semanal, garantindo no máximo um envio por semana, envio na primeira execução seguinte quando a máquina esteve desligada e envio mesmo sem registros pendentes | T052 | - | `memory_card/digest/agendador.py` | 🟡 | `[X]` |
| T054 | Implementar o ponto de entrada que sobe, num único processo, o consumidor do Telegram, o servidor do painel e o agendador do digest | T044, T045, T053 | - | `memory_card/app.py` | 🟡 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T055 | Revisar todas as mensagens enviadas ao chat para que cada erro identifique a etapa que falhou e informe que o material original foi preservado | T041, T044 | `[//]` | `memory_card/captura/respostas.py` | 🟡 | `[X]` |
| T056 | Exibir no painel o custo acumulado de classificação no período selecionado | T034, T046 | `[//]` | `memory_card/painel/visao_periodo.py` | 🟡 | `[X]` |
| T057 | Exibir de forma visualmente distinta, no painel, os registros não classificados e os que falharam em alguma etapa | T046 | `[//]` | `memory_card/painel/visao_periodo.py` | 🟡 | `[X]` |
| T058 | Exibir marcação clara de origem de reunião e de presença de fala de terceiros, no painel e no digest | T046, T051 | `[//]` | `memory_card/painel/registro.py` | 🟡 | `[X]` |
| T059 | Escrever documentação curta de execução: como preencher o `.env`, como subir o processo e como conferir que funcionou | T054 | `[//]` | `README.md` | 🟡 | `[X]` |
| T060 | Construir o instrumento de medição da qualidade da classificação: transcreve, classifica, coleta o julgamento humano amostra a amostra e grava relatório com veredito contra o corte de 4 em 5. **A execução da medição em si não é ação de código**: depende de vinte áudios reais do usuário e de chave de API válida, e está registrada como pendência aberta no adendo | T032 | - | `memory_card/medir.py` | 🔴 | `[X]` |

## Notas de execução

🟡 **Fase 3, defeito encontrado e corrigido no T032.** A primeira implementação de `dividir_em_blocos` só cortava a transcrição em fronteira de frase. Como transcrição de áudio ruidoso frequentemente **não tem pontuação confiável** — que é o caso normal de gravação dirigindo, e a própria spec de transcrição diz isso —, uma reunião inteira voltaria como bloco único, a segunda passagem nunca aconteceria, e o registro sairia com assunto genérico: exatamente o defeito que o componente existe para evitar. Corrigido com corte forçado acima de 1,5× o alvo, mantendo a preferência por fronteira de frase. Verificado com transcrição sem pontuação (2 blocos), com pontuação (3 blocos) e curta (1 bloco, uma passagem só).

🟡 **Fase 3, decisão de implementação não prevista no plano.** `AdaptadorSimulado` foi criado ao lado do adaptador concreto, no mesmo arquivo. Ele não é código de teste escondido em produção: é a demonstração executável de que a fronteira do RF-04 é real. Se algum dia trocar de adaptador exigir mexer em outro arquivo, o T016 falha.

🟡 **Fase 2, correção no T014 durante a escrita do teste.** `ACERVO_TAMANHO_MAX_NOME` limitava apenas o fragmento derivado do assunto, não o nome inteiro. Como o identificador ocupa 23 caracteres fixos, um limite configurado em 80 produzia nomes de 101 caracteres. Isso importa no Windows, cujo teto de 260 caracteres para o caminho completo é consumido rápido por uma pasta de acervo aninhada. O parâmetro passou a limitar o nome inteiro, com o orçamento do assunto calculado por diferença e um piso de segurança para limites absurdamente baixos. Registrado em `progress.jsonl` como `status: corrected`.

🟡 **Fase 3, dependência acrescentada.** `anthropic>=0.116` entrou no `pyproject.toml` para o adaptador concreto do T030. A escolha de provedor continua parametrizada: `LLM_PROVEDOR` seleciona o adaptador, e o adaptador simulado prova que outro fornecedor entra sem tocar no pipeline.

🟡 **T060 permanece aberta, e a razão não é falha.** O instrumento foi construído e é executável — `python -m memory_card.medir <pasta-com-audios>` transcreve, classifica, pergunta amostra por amostra se o usuário aceitaria sem corrigir, e grava relatório em markdown mais dados brutos em JSONL. O relatório já traz o veredito contra o corte de 4 em 5, sinaliza amostra pequena e lista os tipos que nunca foram atribuídos.

A **medição em si** depende de duas coisas que só o usuário tem: vinte áudios reais gravados no contexto real, inclusive dirigindo, e uma chave de API válida. Registrada em `progress.jsonl` como `status: blocked`, não `failed`.

🟡 **T060 não é código e é deliberado.** Ela é o resto do que era o teste Mago de Oz, removido do plano por decisão do usuário em 2026-08-11. Fica como ação executável e obrigatória porque, sem esse número, nenhum ajuste futuro de prompt terá referência para comparação, e o item correspondente do critério de pronto ficaria impossível de fechar.

🟡 **Quatro ações estão marcadas 🔴 e o motivo é o mesmo em todas:** T027, T032, T043 e T060 dependem de valores que ainda não existem, o limite de duração que separa nota curta de áudio longo e o tempo real de transcrição de uma reunião na máquina do usuário. Elas são implementáveis, mas seus parâmetros só se fixam por medição, conforme registrado nas premissas do `roadmap.md#4`.

🟡 **A fase de testes depende de ações do núcleo**, o que parece inversão de ordem e não é. As garantias testadas por T013, T015, T017 e T018 são as que o produto não pode perder, e escrevê-las junto do núcleo, não depois, é o que impede que sejam adiadas indefinidamente. As demais, T011, T012 e T016, dependem apenas da fase de preparação e podem rodar antes de qualquer código de núcleo.

🟡 **`fila-processamento` não possui spec em `_reversa_sdd/sdd/`**, conforme o risco R-06 do roadmap. As ações T035, T036 e T037 o implementam a partir das decisões D-04 e D-01. Rodar `/reversa-sync` após a entrega para convergir esse componente na extração.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-11 | Versão inicial gerada por `/reversa-to-do` | reversa |
