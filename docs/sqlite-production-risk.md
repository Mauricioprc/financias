# Risco do SQLite em produção (PythonAnywhere) — diagnóstico

Só investigação e recomendações — **nenhuma mudança de banco foi feita**.
Ver `ARCHITECTURE.md` seção 5.1 (por que SQLite) e 5.3 (deploy) e
`wsgi_pythonanywhere.py.example` pra contexto do deploy atual.

## 1. O plano free do PythonAnywhere faz backup/snapshot automático do `.db`?

**Não.** Não existe backup ou snapshot automático de arquivos (incluindo o
`instance/financias.db`) em nenhum plano do PythonAnywhere, nem free nem
pago — isso é confirmado em vários tópicos do fórum oficial deles. A única
forma de backup é manual ou via *scheduled task* escrita pelo próprio
usuário.

Ou seja: hoje, se o filesystem do PythonAnywhere corromper o arquivo (ou o
disco tiver um problema, ou um bug apagar/truncar o arquivo por engano),
**não há rede de segurança nenhuma** — a perda é total e sem histórico.

## 2. Esforço de configurar um dump periódico como mitigação mínima

Baixo — é o mitigador mais custo-benefício disponível hoje. Dois
componentes:

### 2.1 Agendamento

O PythonAnywhere free tier tem *scheduled tasks* (aba **Tasks**), mas com
uma pegadinha relevante pro estado atual da conta:

- **Contas free criadas até 2026-01-15**: 1 tarefa agendada por dia,
  rodando até 2h.
- **Contas free criadas depois de 2026-01-15**: **sem acesso a scheduled
  tasks** — o recurso foi removido do free tier pra contas novas.

**Ação necessária antes de decidir a abordagem**: verificar a data de
criação da conta PythonAnywhere que será usada em produção. Se for uma
conta nova (pós 2026-01-15), a única forma de agendar o dump dentro do
próprio PythonAnywhere free não está mais disponível, e a mitigação
precisaria vir de fora (ver 2.3).

### 2.2 O script de dump em si

Trivial — `sqlite3 .backup` (ou até um `shutil.copy` do arquivo, já que
SQLite é um arquivo único) pra um destino externo. Destinos alcançáveis do
free tier (confirmados na allowlist de rede,
`pythonanywhere.com/whitelist/` — todos via HTTPS, que é o único protocolo
liberado no free tier, ver seção 3):

- **Dropbox API** (`.dropboxapi.com`, `.dropbox.com`) — upload via `requests`
  + token de app, sem SDK pesado.
- **Google Drive API** (`.googleapis.com`) — mais setup (OAuth), mas
  também na allowlist.
- **AWS S3** (`.amazonaws.com`) — `boto3` funciona (é tudo HTTPS por
  baixo), storage barato, fácil de rotacionar por lifecycle policy.

Estimativa: **meio dia de trabalho** pra um script robusto (dump +
upload + rotação de N cópias mais antigas + log de sucesso/falha), mais
alguns minutos de setup de credenciais no destino escolhido. S3 é a opção
recomendada — mais simples de rotacionar e mais barato que Drive/Dropbox
pra esse volume.

### 2.3 Se a conta não tiver scheduled tasks (pós 2026-01-15)

Alternativas pra disparar o dump periodicamente sem depender do
agendador do PythonAnywhere:

- **GitHub Actions** com `schedule:` (cron), rodando `curl` num endpoint
  próprio (protegido por uma chave, ex. reaproveitando o padrão de
  `BOT_SERVICE_API_KEY`) que dispara o dump+upload de dentro da própria
  app Flask. Grátis pro volume de uso deste projeto.
- Serviço de cron externo gratuito (ex. cron-job.org) batendo no mesmo
  endpoint.

Isso é mais esforço (precisa criar o endpoint protegido + a automação
externa) — estimativa de **1 dia** em vez de meio dia.

## 3. Alternativas de Postgres gerenciado — allowlist de rede do free tier

**Nenhuma funciona no plano free, e não é por causa da lista de domínios
em si — é por causa do protocolo.** O PythonAnywhere free tier só libera
saída de rede via **HTTP/HTTPS através de um proxy**, pra hosts na
allowlist. O protocolo de fio do Postgres (porta 5432, `libpq`) não é
HTTP — não passa pelo proxy de jeito nenhum, mesmo que o domínio do
provedor esteja na allowlist. Isso é confirmado explicitamente na página
oficial de ajuda deles ("Can I use Postgres on PythonAnywhere?"): conexão
direta a Postgres em qualquer provedor **requer conta paga**.

Verificação por provedor (mesmo com o domínio potencialmente allowlisted,
nenhum resolve o problema de protocolo):

| Provedor | Domínio na allowlist? | Funciona no free tier? |
|---|---|---|
| Neon | não confirmado | **Não** — protocolo Postgres bloqueado |
| ElephantSQL | `.elephantsql.com` sim | **Não** — mesmo motivo |
| Supabase (conexão Postgres direta) | `.supabase.co`/`.supabase.com` sim | **Não** — mesmo motivo |
| AWS RDS Postgres | `.amazonaws.com` sim | **Não** — mesmo motivo |
| Supabase (via REST/PostgREST, não é SQL direto) | sim | Tecnicamente sim, mas exigiria reescrever toda a camada de acesso a dados (SQLAlchemy → chamadas REST) — fora de escopo de "trocar a URL do banco" |

**Conclusão**: enquanto a hospedagem for o free tier do PythonAnywhere,
**não há alternativa de Postgres gerenciado viável** sem reescrever a
camada de dados para HTTP (o que não é uma "troca de banco", é outra
arquitetura). As únicas saídas reais são:

1. Ficar em SQLite + mitigar com dump periódico (seção 2) — recomendado
   pro estágio atual do projeto.
2. Upgrade para o **plano pago do PythonAnywhere** (remove a restrição de
   protocolo — libera qualquer porta/protocolo), aí sim qualquer Postgres
   gerenciado citado acima passa a funcionar sem mudança de código
   (`DATABASE_URL` já é parametrizado, ver `app/config.py`).
3. Migrar a hospedagem pra fora do PythonAnywhere (ex. Render, Railway,
   Fly.io — todos com saída de rede irrestrita mesmo nos planos free) —
   maior esforço, decisão de infraestrutura maior, fora do escopo deste
   relatório.

## Recomendação

Pro estágio atual (uso pessoal/familiar, `ARCHITECTURE.md` seção 5.1):
implementar o dump periódico pra S3 (seção 2.2) como mitigação mínima,
**confirmando antes a data de criação da conta PythonAnywhere** (seção
2.1) pra saber se dá pra usar o agendador nativo deles ou se precisa do
gatilho externo (seção 2.3). Não há necessidade de decidir sobre Postgres
agora — só reconsiderar se/quando o volume de dados, a necessidade de
acesso concorrente real, ou um upgrade de plano mudarem o cálculo.
