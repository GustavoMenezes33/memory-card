# Legacy Impact: 001-captura-voz-ao-arquivo

> Data: `2026-08-11`
> Identificador da feature: `001-captura-voz-ao-arquivo`
> **Feature greenfield, sem legado pré-existente. Âncora: `prd.md` + specs SDD.**
> Execução parcial: Fase 1 (Preparação) concluída, T001 a T010. Fase 2 (Testes) parcialmente concluída, T011 e T012; T013 a T018 aguardam ações do núcleo.

🟡 Não há legado a impactar. Nenhum arquivo pré-existente do projeto foi lido, modificado ou apagado. Todos os arquivos abaixo são **novos**, e o mapeamento aponta para a spec que define o componente, em `_reversa_sdd/sdd/`, no lugar de um `architecture.md` que não existe.

## Arquivos afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `pyproject.toml` | scaffolding | componente-novo | LOW | Estrutura de pacote e declaração de dependências. Sem lógica de negócio |
| `.env.example` | `configuracao` | componente-novo | LOW | Documenta os 39 parâmetros das seções 9.1 das seis specs. Nenhum segredo real |
| `.gitignore` | `configuracao` | componente-novo | MEDIUM | Mantém `.env` e a pasta de dados fora do versionamento. Falha aqui vazaria segredos e o acervo pessoal |
| `memory_card/config.py` | `configuracao` | componente-novo | HIGH | Concentra as três garantias de inicialização: obrigatórios, loopback e coerência do painel. Defeito aqui vira modo permissivo ou painel exposto |
| `memory_card/log.py` | transversal | componente-novo | MEDIUM | Log estruturado com mascaramento de segredo e proibição de registrar conteúdo capturado |
| `config/prompt_classificacao.txt` | `classificacao-ia` | componente-novo | MEDIUM | Sustenta o RF-10 da spec: prompt fora do código, editável sem alteração de implementação |
| `memory_card/**/__init__.py` | scaffolding | componente-novo | LOW | Módulos vazios que delimitam as fronteiras dos seis componentes mais a fila |
| `tests/conftest.py` | `configuracao` | componente-novo | MEDIUM | Isolamento do ambiente de teste: nenhum teste lê o `.env` real nem escreve na pasta de dados real |
| `tests/test_config.py` | `configuracao` | componente-novo | HIGH | 21 testes sobre a validação de obrigatórios, incluindo a garantia de que campo vazio nunca vira modo permissivo |
| `tests/test_config_rede.py` | `configuracao` / `painel-acompanhamento` | componente-novo | HIGH | 17 testes sobre a restrição de loopback e a coerência entre o painel e os links do digest |

## Diff conceitual por componente

### `configuracao`

🟡 Componente que não existia em nenhuma spec como unidade própria: ele emergiu das seções 9.1 acrescentadas às seis specs. Concentra a carga de `.env`, a tipagem dos valores e três validações que o `roadmap.md` classifica como requisitos de segurança, não de conveniência.

🟡 A decisão de reportar **todos** os obrigatórios ausentes de uma vez, e não o primeiro, é implementação e não estava especificada. Relatar um por vez obrigaria o usuário a reiniciar oito vezes para descobrir oito campos faltando.

🟡 A validação de loopback aceita `localhost`, `127.0.0.1` e `::1`, e recusa qualquer outro endereço, inclusive `0.0.0.0`. Verificado por execução.

### `classificacao-ia`

🟡 Apenas o arquivo de prompt foi criado. O prompt já incorpora duas decisões do roadmap que não estavam na spec original: pede `proximos_passos` como **lista** (decisão D-03, reunião com múltiplos encaminhamentos) e exige ação concreta e verificável, listando explicitamente exemplos ruins a evitar.

🟡 Nenhum código de classificação foi escrito ainda. O adaptador concreto é a ação T030.

### Transversal, observabilidade

🟡 `log.py` implementa mascaramento por padrão de segredo e lista de campos sensíveis, incluindo `texto_bruto`. Decorre do requisito de auditoria das specs, que exige registrar operação sem registrar conteúdo.

## Preservadas

🟡 Não aplicável. Projeto greenfield: não existem regras 🟢 extraídas de código, porque não existia código.

## Modificadas

🟡 Não aplicável, pelo mesmo motivo. Nenhum arquivo pré-existente do projeto foi tocado.

🟡 Registro de integridade: os únicos arquivos anteriores neste diretório eram `CLAUDE.md`, `.claude/` e `.reversa/`, todos do próprio framework, e nenhum deles foi lido para modificação nem alterado por esta execução.
