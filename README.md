# Memory Card

Captura de insights por voz em mobilidade. Você fala no Telegram, o áudio é
transcrito na sua máquina, um modelo de linguagem extrai assunto, tipo e
próximos passos, e o registro vira um arquivo markdown no seu disco.

**O problema que ele resolve:** insights ocorrem longe do computador — na rua,
dirigindo, em reunião — e a ferramenta de captura de sempre exige teclado. O
pensamento precisa sobreviver na memória até haver uma máquina, e frequentemente
não sobrevive.

**O que ele não é:** um organizador de notas. O acervo é meio; a ação é fim.

---

## Como funciona

```
você fala no Telegram
        │
        ▼
 sua máquina puxa a mensagem (long polling — nenhuma porta aberta)
        │
        ├── Whisper transcreve, localmente, sem custo
        ├── modelo de linguagem extrai assunto, tipo e próximos passos
        └── grava um .md no seu acervo
        │
        ▼
 bot confirma no chat: "✅ Capturado: <assunto>"

 sexta 19h → digest por e-mail com os pendentes mais antigos
 painel local → quantos viraram ação
```

**Nada exige porta aberta no roteador.** Sua máquina abre a conexão para fora,
como um navegador. O painel escuta apenas em `127.0.0.1` e recusa iniciar em
qualquer outro endereço.

---

## Instalação

```bash
pip install -e .
cp .env.example .env
```

Preencha os **oito obrigatórios** no `.env`. Todos os outros 31 parâmetros têm
padrão e podem ficar em branco.

| Parâmetro | Onde obter |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Fale com o **@BotFather** no Telegram e crie um bot |
| `TELEGRAM_USUARIO_AUTORIZADO` | Seu identificador numérico no Telegram |
| `LLM_API_KEY`, `LLM_PROVEDOR`, `LLM_MODELO` | Do provedor de linguagem escolhido |
| `DIGEST_EMAIL_DESTINO`, `DIGEST_EMAIL_REMETENTE` | Seu e-mail |
| `SMTP_SERVIDOR` | Seu provedor de e-mail |

`SMTP_USUARIO` e `SMTP_SENHA` não entram na validação de inicialização — um
relay local sem autenticação é caso legítimo. Para Gmail ou Outlook, preencha
os dois mesmo assim: em branco, o sistema sobe e só o digest falha.

> **Use senha de aplicativo no SMTP, nunca a senha principal da conta.** Gmail e
> Outlook exigem isso de qualquer forma, e uma senha principal em `.env` é risco
> desproporcional ao benefício.

### Descobrir seu identificador do Telegram

Envie uma mensagem qualquer ao seu bot e rode:

```bash
curl "https://api.telegram.org/bot<SEU_TOKEN>/getUpdates"
```

O número em `message.from.id` é o valor de `TELEGRAM_USUARIO_AUTORIZADO`.

---

## Executar

```bash
memory-card          # ou: python -m memory_card.app
```

Um comando sobe tudo: o consumidor do Telegram, o painel em
`http://localhost:8000` e o agendador do digest.

---

## Conferir que funcionou

Na ordem — cada passo só faz sentido se o anterior passou.

**1. A configuração está travada.** Esvazie `TELEGRAM_USUARIO_AUTORIZADO` e
inicie. O sistema precisa **recusar iniciar**, nomeando o parâmetro. Se subir
assim mesmo, há defeito grave: seria um bot aberto a qualquer pessoa.

**2. Captura por texto.** Mande uma mensagem de texto ao bot. Espere a
confirmação, abra a pasta do acervo e **leia o arquivo em qualquer editor**.
Este é o passo mais importante do checklist: se o arquivo não for legível sem o
sistema, a portabilidade falhou.

**3. Captura por voz.** Grave 30 segundos. Anote o tempo até a confirmação — é
esse número que decide se `WHISPER_MODELO` serve ou precisa ser menor.

**4. As falhas.** São elas que separam "parece funcionar" de "funciona":

| Teste | Esperado |
|---|---|
| Modo avião, gravar, desativar | O Telegram entrega sozinho quando a rede volta |
| Encerrar o processo, mandar mensagem, reiniciar | A mensagem retida é processada |
| Encerrar no meio do processamento | Sem registro duplicado, sem arquivo parcial |
| Pedir a outra pessoa que escreva ao bot | Nada é criado e ela não recebe resposta |
| `LLM_API_KEY` inválida e capturar | Registro **é arquivado assim mesmo**, com o texto íntegro |

O último é o mais importante: perder o insight é inaceitável, perder a estrutura
é recuperável.

**5. Digest.** Ajuste `DIGEST_DIA_SEMANA` e `DIGEST_HORARIO` para daqui a alguns
minutos. Quando o e-mail chegar, **clique num link e confirme que o estado ainda
não mudou** — só o botão de confirmar altera o registro. Se abrir o link já
marcar, há defeito sério: clientes de e-mail pré-carregam links.

---

## Medir a qualidade da classificação

```bash
python -m memory_card.medir <pasta-com-audios>
```

Transcreve os áudios, classifica, pergunta amostra por amostra se você aceitaria
**sem corrigir**, e grava o relatório em
`_reversa_forward/001-captura-voz-ao-arquivo/medicao-classificacao.md`.

Use **áudios reais**, gravados no contexto real, inclusive dirigindo. Texto
digitado à mão mede a classificação sobre a melhor entrada possível e produz um
número otimista que o sistema real não reproduz.

O número não bloqueia nada. Ele existe para que qualquer ajuste futuro de prompt
tenha referência: sem ele, "melhorou" é impressão.

---

## Onde ficam as coisas

```
dados/acervo/2026-08/*.md   seus registros — o único ativo que importa
dados/audios/               áudios originais preservados
dados/indice.json           índice derivado, apagável a qualquer momento
dados/fila/                 trabalho pendente, sobrevive a reinício
dados/custos.jsonl          uma linha por chamada de API
config/prompt_classificacao.txt   edite para melhorar a classificação
```

**A pasta é derivada da data de captura, nunca de uma escolha sua.** É o ponto
central do desenho: dirigindo, ninguém decide categoria — e foi exigir essa
decisão que fez as ferramentas anteriores falharem.

> ⚠️ Alterar `ACERVO_PASTA` depois de haver conteúdo **não move os arquivos
> existentes**. O sistema passa a escrever no caminho novo e o acervo antigo
> fica órfão, invisível ao painel e ao digest.

---

## Testes

```bash
pip install -e ".[dev]"
pytest
```

---

## Privacidade, dito por extenso

| O quê | Onde fica |
|---|---|
| **Acervo** (os arquivos markdown) | **Só na sua máquina** |
| Áudio | Transita pelos servidores do Telegram |
| Transcrição | Transita para o provedor de linguagem |

A concessão foi consciente, em troca de simplicidade. O que permanece local é o
acervo, que é o ativo a preservar.

**Se você gravar reuniões:** o sistema passa a processar fala de terceiros. A
autorização que você pedir aos participantes precisa cobrir não só a gravação,
mas que o áudio será transcrito automaticamente e enviado a um serviço externo.
Consentimento para "posso gravar?" cobre menos do que o sistema faz.
