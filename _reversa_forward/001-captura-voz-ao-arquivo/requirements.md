# Requirements: Captura de voz ao arquivo, fatia fina de ponta a ponta

> Identificador: `001-captura-voz-ao-arquivo`
> Data: `2026-08-11`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

> **Nota de contexto:** projeto greenfield. Não existem `architecture.md`, `domain.md`, `inventory.md` nem `code-analysis.md`, porque não há legado a extrair. As âncoras desta feature são o PRD, as personas e as seis specs SDD produzidas pelo `/reversa-new`. Nenhum item recebe selo 🟢, reservado a fatos extraídos de código existente.

## 1. Resumo executivo

🟡 Entrega a fatia fina que atravessa os seis componentes do sistema, do carro ao arquivo: o usuário grava uma mensagem de voz no Telegram, o áudio é transcrito localmente por Whisper, um modelo de linguagem via API extrai assunto, tipo e próximo passo, e o registro é arquivado como markdown na máquina do usuário, com confirmação devolvida no chat.

🟡 Complementam a fatia um digest semanal por e-mail, que devolve registros pendentes por iniciativa do sistema, e um painel local que exibe as contagens e recebe as marcações de executado ou descartado.

🟡 Resolve o problema de insights ocorrerem longe do teclado e não sobreviverem na memória até haver um computador disponível. Destina-se a um usuário único, em uso pessoal.

🟡 A entrega é condicionada a uma validação prévia: o teste Mago de Oz precisa aprovar a confiabilidade da classificação automática antes de qualquer código, conforme decidido na ideação.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/prd.md#4-escopo-in` | Os oito itens da primeira entrega, dos quais os quatro primeiros formam o escopo mínimo que valida a premissa central | 🟡 |
| `_reversa_sdd/prd.md#6-restrições` | Android, Python, Whisper local, modelo via API, acervo local, painel sem exposição de rede, captura tolerante a falta de sinal | 🟡 |
| `_reversa_sdd/prd.md#8-riscos` | Falha silenciosa, dependência do Telegram, trânsito de conteúdo por terceiros, meia-vida do digest, ponto sem volta na classificação em massa | 🟡 |
| `_reversa_sdd/personas.md#jornada-principal` | Sete passos, da fala ao volante até a execução ou descarte consciente | 🟡 |
| `_reversa_sdd/ideation.md#métricas-de-sucesso` | Quatro registros virando ação por mês, aferidos três meses após a entrega | 🟡 |
| `_reversa_sdd/sdd/captura-telegram.md#6-requisitos-funcionais` | Long polling, autorização por identificador único, confirmação obrigatória no chat, exatamente-uma-vez | 🟡 |
| `_reversa_sdd/sdd/transcricao-whisper.md#6-requisitos-funcionais` | Execução local, custo zero, texto bruto imutável, transcrição vazia como resultado válido | 🟡 |
| `_reversa_sdd/sdd/classificacao-ia.md#6-requisitos-funcionais` | Fronteira única de provedor, conjunto fechado de tipos, arquivamento mesmo sem classificação | 🟡 |
| `_reversa_sdd/sdd/acervo-markdown.md#6-requisitos-funcionais` | Arquivo markdown por registro, pastas derivadas da data, escrita atômica, identificador estável | 🟡 |
| `_reversa_sdd/sdd/digest-semanal.md#6-requisitos-funcionais` | Envio semanal por e-mail, mais antigos primeiro, links de marcação, envio mesmo sem pendentes | 🟡 |
| `_reversa_sdd/sdd/painel-acompanhamento.md#6-requisitos-funcionais` | Escuta apenas em loopback, páginas de confirmação, contagens do período | 🟡 |
| `_reversa_sdd/brainstorms/001-memory-card-anotacoes/decision.md#a-validar-antes-de-comprometer` | Teste Mago de Oz obrigatório antes de qualquer código, corte em discordância acima de um em cinco | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| 🟡 `gustavo-explorador`, modo captura | Registrar um insight sem tirar atenção da direção | Dirigindo, grava uma mensagem de voz no Telegram e recebe confirmação sem tocar em mais nada |
| 🟡 `gustavo-explorador`, modo retomada | Avançar sobre o que registrou | Domingo à noite, recebe o digest por e-mail, abre um registro e executa ou descarta o próximo passo |

🟡 Os dois cenários são a mesma pessoa em momentos com restrições opostas: no primeiro não há atenção disponível, no segundo há deliberação. A hipótese de modelar como duas personas foi avaliada e descartada em `_reversa_sdd/personas.md`.

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Nenhuma decisão de organização pode ser exigida do usuário no momento da captura. Assunto, tipo e pasta são atribuídos pelo sistema. 🟡
   - Origem no legado: n/a, projeto greenfield
   - Tipo: nova
2. **RN-02:** Perder o insight é inaceitável; perder a estrutura é recuperável. Falha de classificação nunca impede o arquivamento do registro. 🟡
   - Origem no legado: n/a
   - Tipo: nova
3. **RN-03:** Nenhuma falha pode ser silenciosa. Toda captura resulta em confirmação ou em erro explícito, e um registro perdido jamais pode aparentar ter sido guardado. 🟡
   - Origem no legado: n/a
   - Tipo: nova
4. **RN-04:** O texto bruto da transcrição é imutável e nunca é sobrescrito por versão refinada, para que reclassificar o acervo não exija reprocessar áudio. 🟡
   - Origem no legado: n/a
   - Tipo: nova
5. **RN-05:** O acervo permanece exclusivamente na máquina do usuário e legível sem nenhum software do projeto. Áudio e transcrição podem transitar por terceiros; o acervo, não. 🟡
   - Origem no legado: n/a
   - Tipo: nova
6. **RN-06:** Nenhum estado de registro pode ser alterado por carregamento de endereço, apenas por ação explícita do usuário. 🟡
   - Origem no legado: n/a
   - Tipo: nova
7. **RN-07:** O sistema atende exclusivamente um usuário, identificado por configuração. Mensagem de qualquer outro remetente é descartada antes de qualquer processamento. 🟡
   - Origem no legado: n/a
   - Tipo: nova
8. **RN-08:** Gravação de reunião só ocorre com autorização verbal dos participantes, obtida no momento da reunião e antes do início da gravação. A obtenção da autorização é responsabilidade do usuário e ocorre fora do sistema; o sistema não a verifica nem a registra. 🟡
   - Origem no legado: n/a
   - Tipo: nova
   - Observação: a autorização pedida aos participantes deve abranger não apenas a gravação, mas também que o conteúdo será transcrito automaticamente e enviado a um serviço externo de processamento de linguagem. Sem isso, o consentimento obtido cobre menos do que o sistema efetivamente faz.
9. **RN-09:** Registros originados de reunião são identificados como tais no acervo, de forma distinta das notas de voz pessoais, por conterem fala de terceiros. 🟡
   - Origem no legado: n/a
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Receber mensagens de voz do Telegram por long polling, sem expor a máquina local à internet | Must | Com o roteador sem portas encaminhadas, uma mensagem enviada do celular é recebida e processada | 🟡 |
| RF-02 | Descartar mensagens de remetente não autorizado antes de qualquer processamento | Must | Mensagem de outra conta não gera arquivo, não recebe resposta e é registrada no log | 🟡 |
| RF-03 | Baixar e preservar o áudio original em disco local | Must | Após o processamento, o arquivo de áudio permanece acessível no caminho configurado | 🟡 |
| RF-04 | Transcrever o áudio localmente com Whisper, sem enviar o conteúdo a serviço externo | Must | Com o modelo já presente, nenhuma requisição de saída ocorre durante a transcrição | 🟡 |
| RF-05 | Extrair assunto, tipo e próximo passo do texto transcrito, via modelo de linguagem por API | Must | Para uma transcrição de teste, os três campos retornam preenchidos e o tipo pertence ao conjunto configurado | 🟡 |
| RF-06 | Arquivar o registro como arquivo markdown com metadados, texto bruto e estado | Must | O arquivo é aberto corretamente em qualquer editor e contém os campos previstos | 🟡 |
| RF-07 | Derivar a pasta de destino automaticamente da data de captura, sem intervenção do usuário | Must | Capturas de meses distintos resultam em pastas distintas sem qualquer interação | 🟡 |
| RF-08 | Responder no chat do Telegram confirmando a captura e o assunto atribuído | Must | Toda mensagem aceita recebe exatamente uma resposta, de confirmação ou de erro | 🟡 |
| RF-09 | Arquivar o registro mesmo quando a classificação falhar, marcando-o como não classificado | Must | Com a API indisponível, o registro existe com o texto bruto íntegro e marcação explícita | 🟡 |
| RF-10 | Processar cada mensagem exatamente uma vez, mesmo após reinício do processo | Must | Interromper e reiniciar durante o processamento não gera registro duplicado | 🟡 |
| RF-11 | Enviar digest semanal por e-mail com registros pendentes, ordenados dos mais antigos primeiro | Must | Com dez pendentes e limite cinco, chegam os cinco de captura mais antiga, nessa ordem | 🟡 |
| RF-12 | Incluir no digest links que abrem página de confirmação no painel local, sem alterar estado ao serem carregados | Must | Carregar o endereço sem confirmar mantém o estado do registro inalterado | 🟡 |
| RF-13 | Permitir marcar registros como executado ou descartado, refletindo a mudança no arquivo markdown | Must | Após a marcação, o arquivo em disco reflete o novo estado e a data e hora da mudança | 🟡 |
| RF-14 | Exibir no painel local as contagens de capturados, arquivados e convertidos em ação no período | Must | Para um mês com quinze capturas e quatro executados, os números exibidos são quinze e quatro | 🟡 |
| RF-15 | Recusar a inicialização do painel quando a interface configurada não for de loopback | Must | Configurar interface externa impede o início e informa que apenas loopback é permitido | 🟡 |
| RF-16 | Ler todos os parâmetros de operação e segredos exclusivamente de `.env` | Must | Removendo um parâmetro obrigatório, a inicialização falha nomeando o parâmetro ausente | 🟡 |
| RF-17 | Aceitar mensagens de texto digitado, tratando-as como transcrição pronta | Should | Enviando texto, o registro é criado sem acionar o Whisper e recebe a mesma confirmação | 🟡 |
| RF-18 | Enviar digest mesmo quando não houver registros pendentes, informando a ausência | Should | Com acervo sem pendentes, o e-mail chega informando isso, em vez de não chegar | 🟡 |
| RF-19 | Alertar, na inicialização do painel, quando o endereço efetivo divergir do usado nos links do digest | Should | Subir o painel em porta diferente da configurada no digest exibe o alerta | 🟡 |
| RF-20 | Manter índice auxiliar reconstruível integralmente a partir dos arquivos do acervo | Should | Apagar o índice e reconstruir produz resultado idêntico ao anterior | 🟡 |
| RF-21 | Aceitar gravação de reunião pelo mesmo canal de captura, marcando o registro resultante como originado de reunião | Must | Um áudio identificado como reunião gera registro cujo metadado de origem o distingue de nota de voz pessoal | 🟡 |
| RF-22 | Aplicar a áudio longo limites de tempo e tratamento de contexto próprios, distintos dos aplicados à nota de voz curta | Must | Um áudio de quarenta e cinco minutos é transcrito e classificado sem atingir o tempo limite da nota curta e sem truncamento silencioso da transcrição | 🟡 |
| RF-23 | Informar ao usuário, ao receber áudio longo, que o processamento levará mais tempo que o habitual | Should | Ao enviar um áudio acima do limite configurado de duração, o chat recebe aviso de processamento estendido antes da confirmação final | 🟡 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Desempenho | Até 60 segundos entre a entrega da mensagem e a confirmação no chat, **para áudio de até 2 minutos** | `_reversa_sdd/sdd/captura-telegram.md#RNF-01`; acima disso o usuário perde a associação entre o que falou e a confirmação | 🟡 |
| Desempenho | Para áudio acima de 2 minutos, o limite de 60 segundos **não se aplica**; vale o aviso de processamento estendido do RF-23 e um tempo limite próprio | Decorre da inclusão de reunião no escopo; aplicar o limite da nota curta a uma reunião de 45 minutos produziria falha por tempo excedido em toda gravação longa | 🟡 |
| Desempenho | Até 45 segundos de transcrição para 1 minuto de áudio na máquina do usuário | `_reversa_sdd/sdd/transcricao-whisper.md#RNF-01`; valor a aferir por medição, pode exigir troca de modelo | 🟡 |
| Desempenho | Painel carrega em até 3 segundos para até 1000 registros | `_reversa_sdd/sdd/painel-acompanhamento.md#RNF-01`; painel lento deixa de ser consultado e perde a função | 🟡 |
| Segurança | Nenhuma porta de entrada aberta; toda comunicação parte da máquina local | `_reversa_sdd/prd.md#6-restrições`, restrição de não exposição de rede | 🟡 |
| Segurança | Painel escuta apenas em loopback, recusando iniciar em interface externa | `_reversa_sdd/sdd/painel-acompanhamento.md#RF-16`; o acervo é o dado mais sensível do sistema | 🟡 |
| Segurança | Segredos exclusivamente em `.env`, fora do controle de versão | Token do bot, chave de API e senha de e-mail; vazamento gera sequestro do bot ou custo financeiro direto | 🟡 |
| Segurança | Autorização por identificador único de usuário, sem modo permissivo em caso de configuração ausente | `_reversa_sdd/sdd/captura-telegram.md#9.1`; ausência do parâmetro deve impedir a inicialização | 🟡 |
| Privacidade | Acervo exclusivamente local; áudio e transcrição transitam por terceiros por concessão consciente | `_reversa_sdd/prd.md#6-restrições`, residência de dados revista na versão 1.1 | 🟡 |
| Privacidade | Com reunião no escopo, o sistema passa a processar **fala de terceiros**, e não apenas do usuário. Registros de reunião são identificados como tais no acervo, conforme RN-09 | Muda a natureza do dado tratado: deixa de ser exclusivamente pessoal. A autorização é obtida fora do sistema, conforme RN-08 | 🟡 |
| Privacidade | A fala de terceiros gravada em reunião transita para o provedor do modelo de linguagem, assim como a do usuário | Consequência direta de RN-08 e da arquitetura decidida no PRD. A autorização pedida aos participantes precisa cobrir esse ponto, não apenas a gravação | 🟡 |
| Confiabilidade | Escrita atômica de registros; nenhuma interrupção pode deixar arquivo parcial | `_reversa_sdd/sdd/acervo-markdown.md#RNF-02`; arquivo parcial é indistinguível de corrupção | 🟡 |
| Confiabilidade | Processamento exatamente-uma-vez com deslocamento de leitura persistido fora da memória do processo | `_reversa_sdd/sdd/captura-telegram.md#RNF-04` | 🟡 |
| Confiabilidade | Falha de qualquer componente externo degrada a função, jamais perde o registro | RN-02; hierarquia entre perder insight e perder estrutura | 🟡 |
| Portabilidade | 100% dos registros legíveis sem nenhum software do projeto | `_reversa_sdd/sdd/acervo-markdown.md#RNF-01`; é a garantia de que o acervo sobrevive ao próprio projeto | 🟡 |
| Observabilidade | Registro de toda mensagem recebida, transcrição, classificação e envio de digest, com custo estimado por chamada de API | O usuário não definiu teto de custo; sem registro, a conta surpreende | 🟡 |
| Observabilidade | Falhas visíveis no painel e no chat, nunca apenas em log | RN-03; falha silenciosa é o modo de defeito mais grave do produto | 🟡 |
| Custo | Custo recorrente limitado à API de classificação; transcrição e armazenamento com custo por uso igual a zero | Decisão do usuário por Whisper local e residência própria | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Captura ao volante com confirmação
  Dado que estou dirigindo e o pipeline está em execução
  Quando gravo uma mensagem de voz no Telegram
  Então recebo no chat uma confirmação com o assunto atribuído
  E um arquivo markdown correspondente existe no acervo local

Cenário: Captura sem sinal de rede
  Dado que gravo a mensagem dentro de um túnel
  Quando a rede é restabelecida
  Então o aplicativo entrega a mensagem sem ação minha
  E o registro é processado normalmente, apenas com atraso

Cenário: Máquina local desligada no momento da captura
  Dado que o pipeline não está em execução
  Quando gravo uma mensagem de voz
  E o pipeline volta a ser iniciado
  Então a mensagem retida é processada
  E recebo a confirmação com o atraso correspondente

Cenário: Classificação indisponível
  Dado que a API do modelo de linguagem está fora do ar
  Quando uma mensagem de voz é capturada
  Então o registro é arquivado com o texto bruto íntegro
  E fica marcado como não classificado
  E recebo no chat um erro identificando a etapa que falhou

Cenário: Digest semanal e conversão em ação
  Dado que existem registros pendentes no acervo
  Quando chega o dia e horário configurados
  Então recebo por e-mail até o limite configurado de registros, dos mais antigos primeiro
  E cada registro traz links de executado e descartado

Cenário: Marcação exige confirmação explícita
  Dado que recebi o digest por e-mail
  Quando o endereço de um link é apenas carregado, sem eu confirmar
  Então o estado do registro permanece inalterado

Cenário: Mensagem de remetente não autorizado
  Dado que um terceiro descobriu o nome do bot
  Quando ele envia uma mensagem
  Então nenhum registro é criado
  E nenhuma resposta é enviada a ele
  E a tentativa é registrada no log

Cenário: Configuração obrigatória ausente
  Dado que o identificador de usuário autorizado não está definido em .env
  Quando o sistema é iniciado
  Então a inicialização falha nomeando o parâmetro ausente
  E em nenhuma hipótese o sistema opera aceitando qualquer remetente

Cenário: Interrupção durante a gravação do registro
  Dado que o processo é encerrado no meio da escrita de um arquivo
  Quando o sistema é reiniciado
  Então ou o arquivo existe íntegro, ou não existe
  E nenhum arquivo parcial permanece no acervo

Cenário: Painel exposto indevidamente
  Dado que a interface de escuta do painel foi configurada para um endereço externo
  Quando o painel é iniciado
  Então a inicialização é recusada
  E a mensagem informa que apenas loopback é permitido

Cenário: Aferição da métrica de sucesso
  Dado um mês com quinze registros capturados e quatro marcados como executados
  Quando abro o painel no período correspondente
  Então vejo quinze capturados e quatro convertidos em ação
  E consigo comparar o resultado com a meta de quatro por mês

Cenário: Captura por texto digitado
  Dado que não posso falar no momento
  Quando envio o insight como mensagem de texto
  Então o registro é criado sem acionar a transcrição
  E recebo a mesma confirmação de uma captura por voz

Cenário: Digest sem registros pendentes
  Dado que não há nenhum registro pendente no acervo
  Quando chega o dia e horário configurados
  Então o e-mail chega informando a ausência de pendentes
  E o ritmo semanal é preservado

Cenário: Divergência entre o painel e os links do digest
  Dado que o painel foi configurado para uma porta diferente da usada nos links do digest
  Quando o painel é iniciado
  Então um alerta de divergência é exibido
  E o endereço efetivo de escuta é informado

Cenário: Reconstrução do índice auxiliar
  Dado que o índice auxiliar foi apagado
  Quando o sistema o reconstrói a partir dos arquivos do acervo
  Então o resultado é idêntico ao anterior
  E nenhum registro é perdido no processo

Cenário: Captura de reunião autorizada
  Dado que obtive autorização verbal dos participantes antes de gravar
  Quando envio a gravação da reunião pelo canal de captura
  Então recebo aviso de que o processamento levará mais tempo que o habitual
  E o registro resultante fica marcado como originado de reunião
  E é distinguível das notas de voz pessoais no acervo

Cenário: Áudio longo não estoura o limite da nota curta
  Dado um áudio de quarenta e cinco minutos
  Quando o pipeline o processa
  Então o tempo limite aplicado é o de áudio longo, não o da nota curta
  E a transcrição é concluída sem truncamento silencioso
  E o registro é arquivado com o texto bruto íntegro
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 a RF-10 | Must | Compõem a fatia mínima do carro ao arquivo; sem eles não há produto nem validação da premissa central |
| RF-11 a RF-13 | Must | Sem devolução e marcação, a métrica de quatro ações por mês nasce zero por construção e não distingue fracasso de desuso |
| RF-14 | Must | Torna a métrica de sucesso aferível; é a única forma de responder se o sistema gera ação ou apenas acumula |
| RF-15, RF-16 | Must | Segurança e configuração; a ausência transforma erro de configuração em exposição de dados ou em modo permissivo |
| RF-17 | Should | Fluxo alternativo de baixo custo, útil quando falar não é possível, mas não é o problema que motivou o projeto |
| RF-18 | Should | Preserva o ritual semanal; silêncio é indistinguível de falha e corrói a confiança no mecanismo |
| RF-19 | Should | Defesa contra digest íntegro com links quebrados, uma falha silenciosa cara de diagnosticar |
| RF-20 | Should | Desempenho de consulta; o acervo funciona sem índice, apenas mais devagar |
| RNF de desempenho | Should | Valores alvo dependem de medição na máquina real e podem exigir troca de modelo de transcrição |
| RF-21, RF-22 | Must | Reunião entrou no escopo por decisão explícita. Sem RF-22, toda gravação longa falharia por tempo excedido, tornando RF-21 inoperante |
| RF-23 | Should | Sem o aviso, o silêncio durante o processamento de uma reunião é indistinguível de falha, contrariando a RN-03 |
| RNF de segurança e privacidade | Must | Decorrem de restrições declaradas pelo usuário e não são negociáveis nesta entrega |

## 9. Esclarecimentos

### Sessão 2026-08-11

- **Q:** O painel será aplicação web local ou interface de terminal?
  **R:** Aplicação web local, servida em endereço de loopback e aberta no navegador. Preserva intactos os links de marcação enviados no digest, que pressupõem navegador. Confirma os requisitos RF-12, RF-13, RF-14, RF-15 e RF-19 como estão redigidos.

- **Q:** Qual o conjunto fechado de tipos de registro que a classificação pode atribuir?
  **R:** Os cinco tipos propostos nas specs: `ideia`, `insight`, `tarefa`, `referencia`, `duvida`. Passam de hipótese a decisão, e permanecem como configuração e não como código, de modo que ajustá-los não exija alteração de implementação nem invalide registros já classificados.

- **Q:** A captura em reunião entra no escopo desta feature?
  **R:** Sim, com gravação da reunião. A autorização é obtida verbalmente dos participantes no momento da reunião, antes do início da gravação. Consequências integradas em RN-08, RF-21, RF-22 e nos requisitos de privacidade.

- **Q:** Qual provedor e modelo de linguagem para a classificação?
  **R:** Nenhum é fixado agora. A escolha permanece parametrizada em `.env`, conforme já previsto na spec de classificação, e será feita mais adiante. A fronteira única de integração é o que torna essa postergação viável sem custo.

- **Q:** Qual o volume real de capturas por semana e qual modelo de Whisper?
  **R:** Cerca de dez capturas por semana, referindo-se a notas de voz curtas. O modelo de Whisper será definido por medição na máquina real, não por escolha antecipada.

## 10. Lacunas

🟡 As três lacunas da versão inicial foram resolvidas na sessão de esclarecimentos acima. Permanecem os pontos abaixo, nenhum bloqueante para o plano.

- 🔴 [DÚVIDA] Áudio de reunião tem ordem de grandeza radicalmente diferente da nota de voz no carro, dezenas de minutos contra dezenas de segundos, e nenhum dos limites atuais foi dimensionado para ele. É preciso decidir se reunião e nota de voz seguem o mesmo caminho de processamento ou caminhos separados, com limites, expectativa de latência e estratégia de classificação próprios. Ver RF-22 e a nota de dimensionamento ao final desta seção.

🟡 **Pontos em aberto que não bloqueiam o plano** e por isso não receberam marcador: qual provedor e modelo de linguagem, decisão deliberadamente adiada e sustentada pela fronteira única de integração; qual modelo de Whisper equilibra qualidade e tempo, a definir por medição; se registros descartados permanecem no lugar ou vão para pasta separada.

🟡 **Nota de dimensionamento.** Dez notas de voz por semana, com duração típica de trinta a sessenta segundos, somam algo entre cinco e dez minutos de áudio semanais, carga que qualquer máquina moderna absorve com folga. **Uma única reunião de quarenta e cinco minutos multiplica esse volume por cerca de cinco a nove vezes**, sozinha. O parâmetro de tempo limite de transcrição, com padrão de trezentos segundos, e o requisito não funcional de confirmação em até sessenta segundos foram ambos escritos para o caso da nota curta e não se sustentam para reunião. É essa desproporção, e não a decisão de gravar, que a lacuna acima registra.

🟡 **Sobre a implementação parametrizada do provedor.** Manter provedor e modelo em configuração não dispensa implementar ao menos um adaptador concreto atrás da fronteira, sem o qual o sistema não classifica nada. O plano precisa prever essa implementação mesmo com a escolha do provedor em aberto.

🟡 **Pendência de processo, resolvida por decisão do usuário em 2026-08-11:** o teste Mago de Oz, que validaria a premissa central desta feature antes de qualquer código, foi **removido do plano**. A justificativa registrada é que o projeto tem também finalidade acadêmica e de aprendizado, de modo que o retorno do esforço não depende de a classificação automática se mostrar confiável.

🟡 **Consequência a carregar:** o RF-05 entra em construção com sua premissa **não validada**. A verificação passa a ocorrer depois, sobre o componente já construído, conforme o passo 3 da ordem de construção do `roadmap.md`. Reprovando, o custo de correção deixa de ser zero e passa a ser de três componentes já implementados. O risco está registrado em `roadmap.md#9`, item R-01, e como premissa explícita em `roadmap.md#4`.

## Pendências de Qualidade

🟡 A auto-validação contra `.reversa/templates/quality-template.md` foi executada. Os itens abaixo permanecem reprovados de forma **deliberada**, após avaliação, e ficam registrados em vez de corrigidos.

### Q-018 | SoluçãoImplícita | Não há nome de biblioteca, framework ou produto comercial no documento

> motivo: o documento nomeia Telegram, Whisper, Android, Python e protocolo de e-mail. Nenhum deles é escolha de implementação deste requirements: todos são **restrições declaradas pelo usuário** e registradas em `_reversa_sdd/prd.md#6-restrições`. Removê-los tornaria os requisitos vagos a ponto de serem inexecutáveis, já que o canal de captura e o local de execução da transcrição são parte do problema, não da solução.
> sugestão: manter os nomes e tratá-los como restrições de contorno. Se alguma delas deixar de valer, o PRD é o documento a revisar primeiro, e este requirements passa a depender dessa revisão.

### Q-017 | SoluçãoImplícita | O requirements descreve o quê, não o como

> motivo: reprovação parcial. O RF-01 menciona long polling e o RF-20 menciona índice auxiliar, que são mecanismos e não comportamentos observáveis. Ambos foram mantidos porque carregam a restrição real que precisa ser preservada: no primeiro caso, que a máquina local não seja exposta à internet; no segundo, que o índice jamais seja fonte da verdade.
> sugestão: em revisão futura, mover o mecanismo para as specs e deixar no requirements apenas a propriedade observável. As specs em `_reversa_sdd/sdd/` já contêm ambos os mecanismos em detalhe.

🟡 Itens não aplicáveis nesta feature, por ausência de legado ou de configuração: **Q-011** (citação de regra original em `domain.md`, inexistente em greenfield), **Q-019** e **Q-020** (princípios do projeto, `.reversa/principles.md` ausente).

🟡 Demais itens da checklist foram avaliados como aprovados. A cobertura Gherkin do **Q-010** foi corrigida durante a auto-validação, com a inclusão de cinco cenários para os requisitos RF-14 e RF-17 a RF-20, que estavam sem cenário na primeira redação.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-08-11 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-08-11 | Auto-validação: cinco cenários Gherkin acrescentados (Q-010) e duas reprovações deliberadas registradas em Pendências de Qualidade | reversa |
| 2026-08-11 | Sessão de esclarecimentos: 3 `[DÚVIDA]` resolvidas. Captura em reunião incluída no escopo, gerando RN-08, RN-09, RF-21, RF-22, RF-23, dois requisitos de privacidade e um de desempenho. Uma lacuna nova aberta sobre dimensionamento de áudio longo | reversa |
