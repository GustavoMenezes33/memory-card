# Deploy em VPS com Docker — Memory Card

Como colocar o Memory Card para rodar 24h numa VPS, dentro de um container.
Pressupõe que o [GUIA-DE-CONFIGURACAO.md](GUIA-DE-CONFIGURACAO.md) já foi
seguido uma vez localmente: você tem o bot, a chave da API e o `.env` funcionando.

---

## Como fica a arquitetura

```
 celular ──Telegram──►  servidores do Telegram  ◄──polling (saída)──┐
                                                                    │
 VPS ┌──────────────────────────────────────────────────────────────┤
     │  container memory-card (network_mode: host)                  │
     │    ├─ consumidor do Telegram ─────────────────────────────────┘
     │    ├─ painel Flask em 127.0.0.1:8000  ◄── tailscale serve / túnel SSH
     │    └─ agendador do digest ──SMTP (saída)──► e-mail
     │  volume ./dados  (acervo, índice, fila, modelos)
     └──────────────────────────────────────────────────────────────
```

- **Nenhuma porta entra na VPS** além do SSH. Telegram e SMTP são conexões de
  saída.
- **O painel continua só em loopback.** `network_mode: host` faz o `127.0.0.1`
  do container ser o da VPS, então a validação de loopback continua valendo e
  nada é publicado para a internet.
- Para abrir o painel de fora, use **Tailscale** (recomendado, funciona no
  celular) ou um **túnel SSH**.

---

## Requisitos da VPS

| Recurso | Mínimo | Confortável |
|---|---|---|
| vCPU | 2 | 4 |
| RAM | 2 GB | 4 GB |
| Disco | 5 GB livres | 10 GB |
| SO | Ubuntu 22.04+ / Debian 12+ | |

O que pesa é a transcrição: o Whisper `small` em int8 usa de 1 a 1,5 GB de RAM
enquanto transcreve.

---

## Passo 1 · Preparar a VPS

Como root, uma vez só:

```bash
# Usuário de trabalho
adduser deploy
usermod -aG sudo deploy
# copie sua chave pública para /home/deploy/.ssh/authorized_keys

# SSH só por chave
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh

# Firewall: só SSH entra
apt update && apt install -y ufw fail2ban
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw enable
```

> **Teste o login como `deploy` por chave numa segunda janela antes de fechar a
> sessão de root.** Se errar a chave, você fica trancado para fora.

### Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker deploy
# saia e entre de novo para o grupo valer
docker compose version
```

---

## Passo 2 · Acesso ao painel

### Opção recomendada: Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

No painel do Tailscale (login.tailscale.com), em **DNS**, ative **MagicDNS** e
**HTTPS Certificates**. Instale o app do Tailscale no celular e no notebook,
com a mesma conta.

O painel é publicado na rede privada no passo 5, depois que o container estiver
de pé.

### Alternativa: túnel SSH

Sem instalar nada na VPS:

```bash
ssh -L 8000:127.0.0.1:8000 deploy@SUA_VPS
```

Enquanto essa sessão estiver aberta, `http://localhost:8000` no seu computador é
o painel da VPS, e os links do digest com `PAINEL_URL_BASE=http://localhost:8000`
funcionam. No celular é inviável, e esse é o motivo de recomendar o Tailscale.

---

## Passo 3 · Código e configuração

```bash
sudo mkdir -p /opt/memory-card && sudo chown deploy:deploy /opt/memory-card
git clone <URL_DO_REPOSITORIO> /opt/memory-card
cd /opt/memory-card
```

O `.env` **não vem pelo git**. Copie o seu da máquina local:

```bash
# na sua máquina
scp .env deploy@SUA_VPS:/opt/memory-card/.env
```

```bash
# na VPS
chmod 600 .env
```

Ajuste no `.env` da VPS:

| Parâmetro | Valor |
|---|---|
| `PAINEL_INTERFACE` | `127.0.0.1` (não mude) |
| `PAINEL_PORTA` | `8000` |
| `PAINEL_URL_BASE` | com Tailscale: `https://<nome-da-vps>.<tailnet>.ts.net`; com túnel SSH: `http://localhost:8000` |

> **Com Tailscale, o log vai emitir um alerta de divergência de endereço** na
> inicialização, porque `PAINEL_URL_BASE` não é mais `localhost:8000`. É
> esperado e não impede nada: os links do digest passam pelo `tailscale serve`,
> que encaminha para a porta 8000.

---

## Passo 4 · Migrar os dados

**Pare a instância local primeiro.** O Telegram não admite dois consumidores do
mesmo bot. Com os dois rodando, as mensagens se dividem entre eles e aparecem
erros 409 no log.

```bash
# na sua máquina, com o sistema local PARADO
rsync -avz --progress dados/ deploy@SUA_VPS:/opt/memory-card/dados/
```

O que importa levar:

| Arquivo | Por quê |
|---|---|
| `dados/acervo/`, `dados/indice.json` | Seus registros |
| `dados/estado_polling.json` | Sem ele, o bot pode reprocessar mensagens antigas que ainda estejam retidas no Telegram |
| `dados/ultimo_digest.json` | Evita enviar de novo o digest de uma semana que já foi enviada |
| `dados/fila/` | Capturas que estavam pela metade |
| `dados/modelos/` | Opcional: poupa o download de ~460 MB na primeira transcrição |

O container roda como UID 1000. Acerte o dono:

```bash
# na VPS
sudo chown -R 1000:1000 /opt/memory-card/dados
```

> Se o seu usuário na VPS tiver outro UID (confira com `id -u`), você pode, em
> vez disso, construir a imagem com o seu: `APP_UID=$(id -u) APP_GID=$(id -g)
> docker compose build`.

---

## Passo 5 · Subir

```bash
cd /opt/memory-card
docker compose up -d --build
docker compose logs -f
```

Espere a linha `painel escutando`. `docker compose ps` deve mostrar o container
como `healthy` depois de cerca de um minuto.

Com Tailscale, publique o painel na rede privada:

```bash
sudo tailscale serve --bg 8000
tailscale serve status
```

Abra `https://<nome-da-vps>.<tailnet>.ts.net` no celular, com o app do
Tailscale conectado.

---

## Passo 6 · Validar ponta a ponta

Os mesmos testes do passo 8 do guia de configuração, agora na VPS:

1. **Texto:** mande uma mensagem ao bot e confira se o arquivo aparece em
   `/opt/memory-card/dados/acervo/AAAA-MM/`.
2. **Voz:** grave uns 30 segundos e **anote o tempo até a confirmação**. CPU de
   VPS costuma ser mais lenta que a de um desktop. Se passar muito de 45 s para
   1 minuto de áudio, use `WHISPER_MODELO=base` no `.env` e rode
   `docker compose up -d`.
3. **Painel:** abra pelo Tailscale ou pelo túnel.
4. **Digest:** force um envio como no passo 8.4 do guia. **Depois apague
   `dados/ultimo_digest.json`** e reinicie, ou o digest de verdade daquela
   semana não sai.

Confirme também o fuso: `docker compose exec memory-card date` deve mostrar o
horário de Brasília.

---

## Operação do dia a dia

| Tarefa | Comando |
|---|---|
| Ver logs | `docker compose logs -f --tail 100` |
| Reiniciar | `docker compose restart` |
| Parar | `docker compose down` |
| Aplicar mudança no `.env` | `docker compose up -d` |
| Atualizar o código | `git pull && docker compose up -d --build` |
| Editar o prompt de classificação | edite `config/prompt_classificacao.txt` e rode `docker compose restart` |
| Medir a classificação | `docker compose exec -it memory-card python -m memory_card.medir dados/audios` |
| Limpar imagens antigas | `docker image prune -f` |

O container volta sozinho depois de um reboot da VPS (`restart: unless-stopped`).
Parar ou reiniciar no meio de uma transcrição não perde a captura: a fila em
`dados/fila` retoma o que estava pendente.

---

## Backup

O acervo agora vive **só na VPS**. Se a VPS sumir, ele some junto. Faça backup
de `dados/`, exceto `modelos/` e `audios/`, que podem ser obtidos de novo.

Exemplo mínimo, um arquivo por dia guardado por 30 dias:

```bash
sudo mkdir -p /var/backups/memory-card
sudo tee /etc/cron.daily/memory-card-backup >/dev/null <<'EOF'
#!/bin/sh
set -e
DEST=/var/backups/memory-card
tar -czf "$DEST/dados-$(date +%F).tar.gz" \
    -C /opt/memory-card dados --exclude=dados/modelos --exclude=dados/audios
find "$DEST" -name 'dados-*.tar.gz' -mtime +30 -delete
EOF
sudo chmod +x /etc/cron.daily/memory-card-backup
```

**Um backup na mesma máquina não protege contra perder a máquina.** Leve as
cópias para fora com `rclone` ou `restic`, de preferência criptografadas, ou
simplesmente puxe para casa de tempos em tempos:

```bash
rsync -avz deploy@SUA_VPS:/var/backups/memory-card/ ./backups-memory-card/
```

---

## Quando algo não funciona

| Sintoma | Causa provável |
|---|---|
| `Configuração inválida` no log e o container reiniciando sem parar | Falta um obrigatório no `.env` da VPS. O erro nomeia qual |
| `PermissionError` em `dados/` | Dono errado. Rode `sudo chown -R 1000:1000 dados` ou construa com o seu UID (passo 4) |
| `Conflict: terminated by other getUpdates request` | Tem outra instância do bot rodando, provavelmente a local. Pare-a |
| `a porta 8000 já está em uso` | Outro serviço da VPS usa a 8000. Mude `PAINEL_PORTA` e `PAINEL_URL_BASE` juntos e refaça o `tailscale serve` com a porta nova |
| Container `unhealthy` | O painel não responde em `127.0.0.1:8000`. Veja `docker compose logs` |
| Container morto, `OOMKilled` em `docker inspect memory-card` | Faltou memória na transcrição. Use `WHISPER_MODELO=base` ou aumente `mem_limit` e a VPS |
| Digest saiu no horário errado | Fuso. Confira `docker compose exec memory-card date` e o `TZ` |
| Painel não abre pelo celular | O app do Tailscale está desconectado, ou falta rodar `tailscale serve --bg 8000` |

---

## Privacidade

Ao ir para a VPS, o acervo, que antes ficava só na sua máquina, passa a ficar no
disco de um provedor. Mitigações que valem a pena:

- Escolha um provedor em que você confie e, se ele oferecer, ative a
  criptografia de disco.
- Mantenha o `.env` com `chmod 600` e nunca o coloque no git ou na imagem. O
  `.dockerignore` já impede que ele entre na imagem.
- Criptografe os backups que saem da VPS.
