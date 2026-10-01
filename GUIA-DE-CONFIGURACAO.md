# Guia de configuração — Memory Card

Da instalação até a primeira captura funcionando. Siga na ordem: cada passo só
faz sentido se o anterior deu certo.

Python 3.12.6 detectado na sua máquina — atende ao mínimo de 3.10.

---

## Passo 1 · Instalar as dependências

```bash
pip install -e .
```

Isso instala o pacote em modo editável e traz as cinco dependências:
`python-dotenv`, `requests`, `flask`, `anthropic` e `faster-whisper`.

> **A primeira instalação demora**, principalmente por causa do `faster-whisper`,
> que traz o motor de transcrição. É normal.

Para rodar os testes depois:

```bash
pip install -e ".[dev]"
```

**Confira:**

```bash
python -c "import faster_whisper, anthropic, flask; print('ok')"
```

---

## Passo 2 · Criar o bot no Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie `/newbot`
3. Escolha um **nome** (aparece no chat, pode ter espaços e acentos)
4. Escolha um **username** — precisa terminar em `bot`, por exemplo
   `gustavo_memory_card_bot`
5. O BotFather responde com o token, no formato
   `123456789:AAH8kQwErTyUiOpAsDfGhJkLzXcVbNm1234`

**Guarde esse token.** Ele é `TELEGRAM_BOT_TOKEN`.

> Um token vazado permite a qualquer pessoa assumir o bot e ler suas capturas.
> Ele vai no `.env`, que já está no `.gitignore`.

---

## Passo 3 · Descobrir o seu identificador do Telegram

O sistema aceita mensagens de **uma pessoa só** — você. Para isso precisa do seu
identificador numérico.

1. **Envie qualquer mensagem** ao bot que você acabou de criar (um "oi" basta).
   Sem isso o próximo comando volta vazio.
2. Rode, trocando `<SEU_TOKEN>` pelo token do passo 2:

```bash
curl "https://api.telegram.org/bot<SEU_TOKEN>/getUpdates"
```

3. Na resposta, procure `"from":{"id":123456789,...}`. Esse número é o seu
   `TELEGRAM_USUARIO_AUTORIZADO`.

> **Se voltar `{"ok":true,"result":[]}`**, você ainda não mandou mensagem ao bot,
> ou mandou para o bot errado. Volte ao passo 1 do procedimento.

---

## Passo 4 · Obter a chave do modelo de linguagem

O sistema usa um modelo de linguagem para extrair assunto, tipo e próximos passos
da transcrição.

1. Crie uma chave em **console.anthropic.com** → *API Keys*
2. Copie o valor — ele só aparece uma vez

Três parâmetros vêm daqui:

| Parâmetro | Valor |
|---|---|
| `LLM_API_KEY` | a chave que você acabou de criar |
| `LLM_PROVEDOR` | `anthropic` |
| `LLM_MODELO` | `claude-opus-5` |

> **Sobre o modelo:** `claude-opus-5` é o mais capaz. A classificação roda com
> esforço baixo, porque é extração estruturada e não raciocínio profundo, então o
> custo por captura é pequeno. Se você preferir gastar menos, `claude-haiku-4-5`
> é bem mais barato — mas essa é a sua escolha, e vale medir a qualidade antes
> de decidir (veja a seção de medição no final).

**Trocar de fornecedor depois é barato**: `LLM_PROVEDOR` seleciona o adaptador, e
a fronteira do sistema foi construída para que trocar exija um arquivo, não uma
reescrita.

---

## Passo 5 · Configurar o e-mail do digest

O digest semanal chega por e-mail. **Use senha de aplicativo, nunca a senha
principal da conta.**

### Se você usa Gmail

1. Ative a verificação em duas etapas na sua Conta Google (obrigatório)
2. Vá em **Segurança → Senhas de app**
3. Gere uma senha para "E-mail" — vem no formato `abcd efgh ijkl mnop`
4. Use essa senha, **sem os espaços**, em `SMTP_SENHA`

| Parâmetro | Valor para Gmail |
|---|---|
| `SMTP_SERVIDOR` | `smtp.gmail.com` |
| `SMTP_PORTA` | `587` |
| `SMTP_USUARIO` | seu e-mail completo |
| `SMTP_SENHA` | a senha de app, sem espaços |
| `DIGEST_EMAIL_REMETENTE` | seu e-mail |
| `DIGEST_EMAIL_DESTINO` | seu e-mail (o mesmo, provavelmente) |

### Outlook / Hotmail

`smtp-mail.outlook.com`, porta `587`, também com senha de aplicativo.

> **`SMTP_USUARIO` e `SMTP_SENHA` não são verificados na inicialização.** Só
> `SMTP_SERVIDOR` é. Isso é proposital — um relay local sem autenticação é caso
> legítimo — mas tem uma consequência: se você deixar as credenciais em branco,
> o sistema sobe normalmente e a falha só aparece no primeiro envio do digest,
> **sexta às 19:00**. Preencha agora, ou force um envio de teste no passo 8.4
> em vez de esperar uma semana para descobrir.

---

## Passo 6 · Preencher o `.env`

```bash
cp .env.example .env
```

Abra o `.env` e preencha os campos abaixo. Os outros têm padrão e podem ficar
exatamente como estão.

Duas categorias diferentes, e a diferença importa:

- **Os oito obrigatórios** — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USUARIO_AUTORIZADO`,
  `LLM_API_KEY`, `LLM_PROVEDOR`, `LLM_MODELO`, `DIGEST_EMAIL_DESTINO`,
  `DIGEST_EMAIL_REMETENTE` e `SMTP_SERVIDOR`. Sem qualquer um deles o sistema
  **não inicia**, e o erro nomeia todos os que faltam de uma vez.
- **`SMTP_USUARIO` e `SMTP_SENHA`** — necessários na prática para o digest sair,
  mas **não verificados na inicialização** (veja o aviso no passo 5).

```env
TELEGRAM_BOT_TOKEN=123456789:AAH8kQwErTyUiOpAsDfGhJkLzXcVbNm1234
TELEGRAM_USUARIO_AUTORIZADO=123456789

LLM_API_KEY=sua-chave-aqui
LLM_PROVEDOR=anthropic
LLM_MODELO=claude-opus-5

DIGEST_EMAIL_DESTINO=voce@gmail.com
DIGEST_EMAIL_REMETENTE=voce@gmail.com
SMTP_SERVIDOR=smtp.gmail.com
SMTP_USUARIO=voce@gmail.com
SMTP_SENHA=abcdefghijklmnop
```

### Confira que a validação funciona

Antes de iniciar de verdade, apague o valor de `TELEGRAM_USUARIO_AUTORIZADO`,
deixando a linha vazia, e rode:

```bash
memory-card
```

**Esperado:** o sistema recusa iniciar e diz qual parâmetro está faltando.

```
Configuração inválida:
  Parâmetros obrigatórios ausentes no .env: TELEGRAM_USUARIO_AUTORIZADO.
  Consulte .env.example. O sistema não inicia sem eles, e em nenhuma
  hipótese opera em modo permissivo.
```

Se ele **subir** com o campo vazio, pare: seria um bot aberto a qualquer pessoa
que descobrisse o nome dele. Restaure o valor e siga.

---

## Passo 7 · Iniciar

```bash
memory-card
```

Equivalente, se preferir: `python -m memory_card.app`

Um comando sobe as três coisas:

| Componente | Onde |
|---|---|
| Consumidor do Telegram | conexão de saída, nenhuma porta aberta |
| Painel | `http://localhost:8000` |
| Agendador do digest | verifica o relógio a cada minuto |

Você verá o log estruturado no terminal e a linha `painel escutando`.

> **A primeira captura por voz demora mais.** O modelo de transcrição
> (`small`, cerca de 460 MB) é baixado uma única vez, na primeira vez que houver
> áudio para transcrever. As seguintes usam o modelo já em disco.

Para encerrar: `Ctrl+C`.

---

## Passo 8 · Primeira captura

Na ordem — cada passo verifica algo diferente.

### 8.1 Texto (o caminho mais curto)

1. Mande uma mensagem de **texto** ao bot: *"testar se a captura funciona"*
2. Espere a confirmação com o assunto atribuído
3. Abra `dados/acervo/2026-08/` e **leia o arquivo em qualquer editor**

**Este é o passo mais importante do guia.** Se o arquivo não for legível sem o
sistema rodando, a promessa central do produto falhou. Ele deve ter o cabeçalho
de metadados no topo e o texto original abaixo.

### 8.2 Voz

1. Segure o botão do microfone no Telegram e fale por uns 30 segundos
2. **Anote o tempo** entre enviar e receber a confirmação

Esse número decide se `WHISPER_MODELO` serve. Se passar muito de 45 segundos
para 1 minuto de áudio, troque para `base` no `.env` e meça de novo.

### 8.3 Painel

Abra `http://localhost:8000`. Você deve ver as contagens e os registros.

Tente abrir de **outro aparelho da rede** — a conexão precisa ser recusada. O
acervo é o dado mais sensível do sistema, e ele não é publicado.

### 8.4 Digest

1. No `.env`, ajuste para o dia de hoje e um horário que **já passou** — assim o
   envio sai no minuto seguinte, sem esperar:

```env
DIGEST_DIA_SEMANA=quarta
DIGEST_HORARIO=20:30
```

2. Reinicie o sistema e espere o e-mail chegar
3. **Clique num link e confirme que o estado ainda não mudou** — deve abrir uma
   página pedindo confirmação
4. Confirme na página e veja o registro mudar de estado
5. Restaure `sexta` e `19:00`
6. **Apague `dados/ultimo_digest.json`** e reinicie — veja o porquê abaixo

O passo 3 é a verificação de integridade: clientes de e-mail pré-carregam links,
e se abrir já marcasse, seus registros seriam marcados sozinhos.

> **O passo 6 não é limpeza, é o conserto de um efeito colateral.** O agendador
> controla o envio **por semana ISO**, não por data: ele anota em
> `dados/ultimo_digest.json` que a semana já foi enviada, e é isso que impede
> receber três digests acumulados depois de uma viagem.
>
> Consequência: um teste na quarta consome o envio da **mesma semana ISO**, que
> vai de segunda a domingo. A sexta seguinte cai dentro dela, e o digest de
> verdade **não sai** — sem erro, sem aviso, só silêncio. Apagar esse arquivo
> rearma o envio. Ele é registro de controle, não acervo; apagar não perde
> nenhum registro seu.

---

## Passo 9 · Deixar rodando

O sistema precisa estar em execução para capturar. Se ele estiver desligado
quando você gravar, **nada se perde** — o Telegram retém a mensagem e ela é
processada quando você voltar a subir. Mas a confirmação só chega depois.

Para uso de verdade, deixe rodando na máquina que você usa no dia a dia.

**O digest é a exceção: ele não é retomado na semana seguinte.** O agendador
verifica, a cada minuto, se o momento da semana já passou e se esta semana ainda
não foi enviada. A janela de recuperação vai do horário configurado até a virada
da semana ISO, que acontece **na meia-noite de domingo**: se a máquina estiver
ligada em qualquer minuto desse intervalo, o envio sai. Depois disso a semana
vira, o alvo passa a ser a ocorrência seguinte, e o digest daquela semana
simplesmente não acontece.

É deliberado: acumular envios atrasados é a forma mais rápida de fazer alguém
ignorar o ritual semanal.

**É por isso que o padrão recomendado é `sexta` / `19:00`.** A janela vai da
sexta às 19:00 até a meia-noite de domingo — mais de dois dias para a máquina
estar ligada em algum momento. Com `domingo` / `19:00` a janela seria de cinco
horas, e um domingo à noite fora de casa custaria o digest da semana. Escolha o
dia pensando nisso: quanto mais cedo na semana, maior a folga.

---

## Medir a qualidade da classificação

Depois de uma semana capturando, com uns vinte áudios reais:

```bash
python -m memory_card.medir dados/audios
```

Ele transcreve, classifica e pergunta amostra por amostra se você aceitaria
**sem corrigir**. Grava o relatório em
`_reversa_forward/001-captura-voz-ao-arquivo/medicao-classificacao.md`.

Duas coisas que o relatório te diz e que você não descobre de outro jeito:

- A **taxa de concordância** — se ficar abaixo de 4 em 5, o primeiro ajuste é
  `config/prompt_classificacao.txt`, que é editável sem tocar em código
- Quais **tipos nunca foram atribuídos** — os cinco em `LLM_TIPOS_REGISTRO` foram
  escolhidos por hipótese, não por observação do seu material

---

## Quando algo não funciona

| Sintoma | Causa provável |
|---|---|
| `Configuração inválida` ao iniciar | Falta um dos oito obrigatórios; o erro nomeia qual |
| `Painel não pode iniciar: a porta 8000 já está em uso` | Outro processo na porta. **O sistema não escolhe outra sozinho**, porque isso quebraria os links dos digests já enviados. Libere a porta, ou mude `PAINEL_PORTA` **e** `PAINEL_URL_BASE` juntos |
| Alerta de divergência de endereço no log | Você mudou `PAINEL_PORTA` sem mudar `PAINEL_URL_BASE`. O painel funciona, mas os links do digest apontam para lugar nenhum |
| `getUpdates` volta vazio | Você não mandou mensagem ao bot ainda |
| Bot não responde nada | O `TELEGRAM_USUARIO_AUTORIZADO` não bate com o seu. Mensagem de remetente não autorizado é descartada em silêncio, de propósito |
| Registro arquivado "sem classificação" | A API falhou. **O insight foi preservado** com o texto íntegro — só a estrutura faltou, e é recuperável |
| Transcrição muito lenta | Troque `WHISPER_MODELO` para `base` |
| E-mail não chega | Se o erro citar autenticação, `SMTP_USUARIO`/`SMTP_SENHA` estão em branco (não são checados na inicialização) ou a senha de app foi revogada. Se citar indisponibilidade, é transitório e o envio sai na semana seguinte |
| Chegou o dia do digest e ele não saiu, sem erro no log | O envio desta semana já foi consumido — por um teste do passo 8.4, ou por um envio anterior na mesma semana ISO (segunda a domingo). Confira `dados/ultimo_digest.json`: se `semana` for a semana corrente, foi isso. Apague o arquivo para rearmar |
| O digest não saiu e a semana já virou | A máquina ficou desligada da hora marcada até a meia-noite de domingo. Não há reposição na semana seguinte, de propósito. Se for recorrente, antecipe `DIGEST_DIA_SEMANA` para ganhar janela |

---

## O que você precisa saber sobre privacidade

| O quê | Onde fica |
|---|---|
| **Acervo** (os arquivos markdown) | **Só na sua máquina** |
| Áudio | Transita pelos servidores do Telegram |
| Transcrição | Transita para o provedor do modelo |

Se você gravar reuniões, o sistema passa a processar fala de terceiros. A
autorização que você pedir aos participantes precisa cobrir não só a gravação,
mas que o áudio será transcrito e enviado a um serviço externo.
