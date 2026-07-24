# ARCHITECTURE.md

Sistema de gestão financeira pessoal — Fase 0 (fundação).

Stack: Flask + PostgreSQL (Neon) + SQLAlchemy + Alembic. Backend hospedado no
Render (free tier). Duas interfaces futuras (dashboard web, chatbot WhatsApp via
Meta Cloud API) consumindo a mesma API e o mesmo banco.

Este documento cobre apenas planejamento. Nenhum código de implementação é
criado nesta fase. Fase 1 (autenticação + CRUD de receitas/despesas) só começa
após aprovação explícita.

---

## 1. Estrutura de pastas

Monorepo único, com o backend Flask como núcleo e as duas interfaces (web,
bot) como consumidores externos da API — nunca acessando o banco diretamente.

```
financias/
├── ARCHITECTURE.md
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml              # config de lint/format/type-check
├── wsgi.py                     # entrypoint do Render (gunicorn wsgi:app)
│
├── app/                        # pacote principal do backend Flask
│   ├── __init__.py             # application factory (create_app)
│   ├── config.py               # classes de config (Dev/Prod/Test) via env vars
│   ├── extensions.py           # instâncias compartilhadas: db, migrate, jwt, etc.
│   │
│   ├── models/                 # SQLAlchemy models (1 arquivo por entidade/domínio)
│   │   ├── __init__.py
│   │   ├── base.py             # Base declarativa + mixins (TimestampMixin, etc.)
│   │   ├── user.py
│   │   ├── account.py          # contas bancárias
│   │   ├── category.py
│   │   ├── transaction.py      # receitas/despesas
│   │   ├── credit_card.py
│   │   ├── invoice.py          # faturas de cartão
│   │   ├── goal.py             # metas financeiras
│   │   ├── investment.py
│   │   └── recurring_transaction.py
│   │
│   ├── schemas/                # (de)serialização e validação (Marshmallow/Pydantic)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── transaction.py
│   │   └── ...                 # espelha 1:1 os models relevantes
│   │
│   ├── services/                # lógica de negócio, orquestração, regras
│   │   ├── __init__.py
│   │   ├── auth_service.py      # login, emissão/validação de JWT
│   │   ├── user_service.py
│   │   ├── transaction_service.py
│   │   ├── invoice_service.py   # fechamento/geração de fatura
│   │   ├── recurring_service.py # geração de transações a partir de recorrências
│   │   └── goal_service.py
│   │
│   ├── api/                     # camada HTTP fina — só request/response, chama services
│   │   ├── __init__.py
│   │   ├── errors.py            # handlers globais de erro + formato padrão
│   │   ├── decorators.py        # ex: @require_user, @validate_schema
│   │   └── v1/
│   │       ├── __init__.py      # blueprint registration (prefixo /api/v1)
│   │       ├── auth_routes.py
│   │       ├── user_routes.py
│   │       ├── account_routes.py
│   │       ├── transaction_routes.py
│   │       ├── credit_card_routes.py
│   │       ├── invoice_routes.py
│   │       ├── goal_routes.py
│   │       ├── investment_routes.py
│   │       └── recurring_routes.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── datetime_utils.py
│       └── money.py             # helpers de precisão decimal/moeda
│
├── migrations/                  # Alembic (via Flask-Migrate)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/
│   ├── conftest.py
│   ├── unit/                    # testa services isoladamente (banco de teste)
│   └── integration/             # testa rotas da API fim a fim
│
├── web/                         # frontend do dashboard (futuro — projeto separado)
│   └── README.md                # placeholder: SPA (React/Vue) consumindo /api/v1
│
└── bot/                         # integração WhatsApp (futuro)
    └── README.md                # placeholder: webhook Meta Cloud API -> /api/v1
```

**Racional das fronteiras:**

- `models/` só descreve estrutura de dados e relacionamentos — sem regra de negócio.
- `services/` é a única camada que pode ter lógica condicional relevante
  (ex.: "fechar fatura", "gerar transação recorrente do mês"). Isso é o que
  permite que `web` e `bot` reutilizem exatamente a mesma regra no futuro,
  porque ambos vão bater na mesma API, que chama os mesmos services.
- `api/` é intencionalmente burra: valida entrada, chama o service, formata
  saída. Isso mantém a lógica testável sem precisar subir um servidor HTTP.
- `web/` e `bot/` hoje são só placeholders — quando forem implementados, serão
  clientes HTTP da API, não terão acesso direto ao banco. Isso é o que garante
  que multi-interface não vire multi-fonte-de-verdade.

---

## 2. DER — Modelo de dados

Convenção geral: toda tabela de domínio tem `id` (PK, integer ou UUID — ver
nota abaixo), `user_id` (FK para `users.id`, obrigatório, indexado) e
`created_at` / `updated_at`. Isso implementa multi-tenancy **row-level**: um
único schema, um único banco, todo dado sempre filtrado por `user_id` na
camada de service. Não há schema-per-tenant nem database-per-tenant.

> Nota sobre PKs: recomendo `id` como `BIGINT` autoincremento para simplicidade
> e performance de índice, em vez de UUID. Como não há sincronização
> offline nem exposição de IDs sequenciais sensível (é uso pessoal), não há
> motivo forte para UUID agora. Se isso for uma preocupação, é uma troca
> pequena e isolada em `models/base.py`.

### 2.1 `users`

| Coluna          | Tipo         | Constraints                     | Notas |
|-----------------|--------------|----------------------------------|-------|
| id              | BIGINT       | PK                                | |
| name            | VARCHAR(120) | NOT NULL                         | |
| email           | VARCHAR(255) | NOT NULL, UNIQUE                 | login do dashboard |
| password_hash   | VARCHAR(255) | NOT NULL                         | bcrypt/argon2 |
| phone_number    | VARCHAR(20)  | UNIQUE, NULLABLE                 | formato E.164 (+55...); usado pelo bot |
| timezone        | VARCHAR(50)  | NOT NULL, DEFAULT 'America/Sao_Paulo' | |
| is_active       | BOOLEAN      | NOT NULL, DEFAULT true            | |
| created_at      | TIMESTAMPTZ  | NOT NULL, DEFAULT now()           | |
| updated_at      | TIMESTAMPTZ  | NOT NULL, DEFAULT now()           | |

Esta é a única tabela sem `user_id` próprio (ela É o tenant).

### 2.2 `accounts` (contas bancárias / carteiras)

| Coluna          | Tipo          | Constraints                          | Notas |
|-----------------|---------------|----------------------------------------|-------|
| id              | BIGINT        | PK                                     | |
| user_id         | BIGINT        | FK -> users.id, NOT NULL, INDEX        | |
| name            | VARCHAR(100)  | NOT NULL                               | ex: "Nubank", "Carteira" |
| type            | VARCHAR(30)   | NOT NULL                               | enum: checking, savings, wallet, other |
| initial_balance | NUMERIC(14,2) | NOT NULL, DEFAULT 0                    | |
| current_balance | NUMERIC(14,2) | NOT NULL, DEFAULT 0                    | atualizado via transações |
| currency        | CHAR(3)       | NOT NULL, DEFAULT 'BRL'                | |
| is_archived     | BOOLEAN       | NOT NULL, DEFAULT false                | |
| created_at      | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                | |
| updated_at      | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                | |

### 2.3 `categories`

| Coluna     | Tipo         | Constraints                    | Notas |
|------------|--------------|----------------------------------|-------|
| id         | BIGINT       | PK                                | |
| user_id    | BIGINT       | FK -> users.id, NOT NULL, INDEX   | |
| name       | VARCHAR(80)  | NOT NULL                          | |
| type       | VARCHAR(10)  | NOT NULL                          | enum: income, expense |
| parent_id  | BIGINT       | FK -> categories.id, NULLABLE     | subcategorias |
| icon       | VARCHAR(50)  | NULLABLE                          | |
| color      | VARCHAR(7)   | NULLABLE                          | hex |
| is_system  | BOOLEAN      | NOT NULL, DEFAULT false           | categorias padrão seedadas |
| created_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now()           | |

Constraint: `UNIQUE(user_id, name, type)`.

### 2.4 `transactions` (receitas/despesas)

| Coluna              | Tipo          | Constraints                              | Notas |
|---------------------|---------------|---------------------------------------------|-------|
| id                  | BIGINT        | PK                                          | |
| user_id             | BIGINT        | FK -> users.id, NOT NULL, INDEX             | |
| account_id          | BIGINT        | FK -> accounts.id, NOT NULL, INDEX          | |
| category_id         | BIGINT        | FK -> categories.id, NULLABLE               | |
| credit_card_id      | BIGINT        | FK -> credit_cards.id, NULLABLE             | preenchido se pago no cartão |
| invoice_id          | BIGINT        | FK -> invoices.id, NULLABLE, INDEX          | fatura a que pertence, se aplicável |
| recurring_id        | BIGINT        | FK -> recurring_transactions.id, NULLABLE   | origem, se gerada automaticamente |
| type                | VARCHAR(10)   | NOT NULL                                    | enum: income, expense |
| description         | VARCHAR(255)  | NOT NULL                                    | |
| amount              | NUMERIC(14,2) | NOT NULL, CHECK (amount > 0)                | valor sempre positivo; sinal vem de `type` |
| date                | DATE          | NOT NULL, INDEX                             | data de competência |
| is_paid             | BOOLEAN       | NOT NULL, DEFAULT true                      | false = previsto/pendente |
| installment_number  | SMALLINT      | NULLABLE                                    | ex: 2 de 12 |
| installment_total   | SMALLINT      | NULLABLE                                    | |
| purchase_group_id   | UUID          | NULLABLE, INDEX                             | amarra todas as parcelas da mesma compra |
| notes               | TEXT          | NULLABLE                                    | |
| created_at          | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                     | |
| updated_at          | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                     | |

Índice composto recomendado: `(user_id, date)` para queries de extrato/período.

`purchase_group_id` existe porque `installment_number`/`installment_total`
descrevem a posição da parcela ("2 de 12"), mas não amarram as parcelas de
uma mesma compra entre si — sem esse campo não há como saber quais linhas de
`transactions` pertencem à mesma compra parcelada. Todas as parcelas geradas a
partir de uma mesma compra compartilham o mesmo `purchase_group_id` (gerado
uma vez no momento da criação da compra parcelada); transações avulsas
(não parceladas) ficam com `purchase_group_id = NULL`. Isso é o que permite
que o futuro `transaction_service` edite ou cancele a compra inteira (todas as
parcelas futuras, `is_paid = false`) em uma única operação, em vez de exigir
que o usuário edite parcela por parcela.

### 2.5 `credit_cards`

| Coluna         | Tipo          | Constraints                       | Notas |
|----------------|---------------|--------------------------------------|-------|
| id             | BIGINT        | PK                                   | |
| user_id        | BIGINT        | FK -> users.id, NOT NULL, INDEX      | |
| name           | VARCHAR(100)  | NOT NULL                             | ex: "Nubank Ultravioleta" |
| credit_limit   | NUMERIC(14,2) | NOT NULL                             | |
| closing_day    | SMALLINT      | NOT NULL, CHECK (1-31)               | dia de fechamento |
| due_day        | SMALLINT      | NOT NULL, CHECK (1-31)               | dia de vencimento |
| is_archived    | BOOLEAN       | NOT NULL, DEFAULT false              | |
| created_at     | TIMESTAMPTZ   | NOT NULL, DEFAULT now()              | |

### 2.6 `transfers` (transferências entre contas)

| Coluna          | Tipo          | Constraints                                          | Notas |
|-----------------|---------------|-------------------------------------------------------|-------|
| id              | BIGINT        | PK                                                     | |
| user_id         | BIGINT        | FK -> users.id, NOT NULL, INDEX                        | |
| from_account_id | BIGINT        | FK -> accounts.id, NOT NULL, INDEX                     | |
| to_account_id   | BIGINT        | FK -> accounts.id, NOT NULL, INDEX                     | |
| amount          | NUMERIC(14,2) | NOT NULL, CHECK (amount > 0)                           | |
| date            | DATE          | NOT NULL                                               | |
| description     | VARCHAR(255)  | NULLABLE                                               | |
| created_at      | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                                | |

Constraint: `CHECK (from_account_id <> to_account_id)`.

**Importante:** `transfers` é uma entidade separada de `transactions` — uma
transferência entre duas contas do próprio usuário (ex. "Nubank" → "Carteira")
não é receita nem despesa, é apenas movimentação de saldo entre ativos que já
são dele. Por isso, criar um `transfer` **não gera nenhuma linha em
`transactions`** e **não deve contar em relatórios de receita/despesa**
(extrato mensal, categorias, metas). O único efeito de um `transfer` é: debitar
`amount` de `from_account_id.current_balance` e creditar `amount` em
`to_account_id.current_balance`, ambos no mesmo `transfer_service` (a criar na
fase de implementação), como operação atômica.

### 2.7 `invoices` (faturas de cartão)

| Coluna          | Tipo          | Constraints                            | Notas |
|-----------------|---------------|--------------------------------------------|-------|
| id              | BIGINT        | PK                                          | |
| user_id         | BIGINT        | FK -> users.id, NOT NULL, INDEX             | |
| credit_card_id  | BIGINT        | FK -> credit_cards.id, NOT NULL, INDEX      | |
| reference_month | DATE          | NOT NULL                                    | primeiro dia do mês de referência |
| closing_date    | DATE          | NOT NULL                                    | |
| due_date        | DATE          | NOT NULL                                    | |
| total_amount    | NUMERIC(14,2) | NOT NULL, DEFAULT 0                         | soma das transactions vinculadas |
| status          | VARCHAR(20)   | NOT NULL, DEFAULT 'open'                    | enum: open, closed, paid |
| paid_at         | TIMESTAMPTZ   | NULLABLE                                    | |
| created_at      | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                     | |

Constraint: `UNIQUE(credit_card_id, reference_month)`.

### 2.8 `goals` (metas financeiras)

| Coluna         | Tipo          | Constraints                    | Notas |
|----------------|---------------|------------------------------------|-------|
| id             | BIGINT        | PK                                  | |
| user_id        | BIGINT        | FK -> users.id, NOT NULL, INDEX     | |
| name           | VARCHAR(120)  | NOT NULL                            | ex: "Reserva de emergência" |
| target_amount  | NUMERIC(14,2) | NOT NULL                            | |
| current_amount | NUMERIC(14,2) | NOT NULL, DEFAULT 0                 | |
| target_date    | DATE          | NULLABLE                            | |
| status         | VARCHAR(20)   | NOT NULL, DEFAULT 'in_progress'     | enum: in_progress, achieved, abandoned |
| created_at     | TIMESTAMPTZ   | NOT NULL, DEFAULT now()             | |
| updated_at     | TIMESTAMPTZ   | NOT NULL, DEFAULT now()             | |

### 2.9 `investments`

| Coluna         | Tipo          | Constraints                       | Notas |
|----------------|---------------|---------------------------------------|-------|
| id             | BIGINT        | PK                                     | |
| user_id        | BIGINT        | FK -> users.id, NOT NULL, INDEX        | |
| name           | VARCHAR(120)  | NOT NULL                               | ex: "Tesouro Selic 2029" |
| type           | VARCHAR(30)   | NOT NULL                               | enum: fixed_income, stock, fund, crypto, other |
| broker         | VARCHAR(100)  | NULLABLE                               | |
| invested_amount| NUMERIC(14,2) | NOT NULL                               | total aportado |
| current_amount | NUMERIC(14,2) | NOT NULL                               | valor de mercado atual |
| acquired_at    | DATE          | NOT NULL                               | |
| notes          | TEXT          | NULLABLE                               | |
| created_at     | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                | |
| updated_at     | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                | |

*(Fase 0 mantém isso simples — sem histórico de cotação por enquanto; pode
virar tabela `investment_snapshots` no futuro se for necessário.)*

### 2.10 `recurring_transactions` (assinaturas, salário, parcelas fixas)

| Coluna         | Tipo          | Constraints                        | Notas |
|----------------|---------------|----------------------------------------|-------|
| id             | BIGINT        | PK                                     | |
| user_id        | BIGINT        | FK -> users.id, NOT NULL, INDEX        | |
| account_id     | BIGINT        | FK -> accounts.id, NOT NULL            | |
| category_id    | BIGINT        | FK -> categories.id, NULLABLE          | |
| description    | VARCHAR(255)  | NOT NULL                               | ex: "Salário", "Netflix" |
| type           | VARCHAR(10)   | NOT NULL                               | enum: income, expense |
| amount         | NUMERIC(14,2) | NOT NULL                               | |
| frequency      | VARCHAR(20)   | NOT NULL                               | enum: monthly, weekly, yearly |
| day_of_month   | SMALLINT      | NULLABLE, CHECK (1-31)                 | usado se frequency=monthly |
| start_date     | DATE          | NOT NULL                               | |
| end_date       | DATE          | NULLABLE                               | null = indeterminado |
| last_generated | DATE          | NULLABLE                               | controla geração idempotente |
| is_active      | BOOLEAN       | NOT NULL, DEFAULT true                 | |
| created_at     | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                | |
| updated_at     | TIMESTAMPTZ   | NOT NULL, DEFAULT now()                | |

`recurring_service` usa `last_generated` para criar as `transactions`
correspondentes (via job agendado ou verificação lazy no request), setando
`transactions.recurring_id`.

### 2.11 Relacionamentos (resumo)

```
users 1───N accounts
users 1───N categories (self-referencing parent_id)
users 1───N credit_cards
users 1───N transfers
users 1───N goals
users 1───N investments
users 1───N recurring_transactions
users 1───N transactions
users 1───N invoices

accounts 1───N transactions
accounts 1───N recurring_transactions
accounts 1───N transfers (from_account_id)
accounts 1───N transfers (to_account_id)

credit_cards 1───N invoices
credit_cards 1───N transactions (opcional)

invoices 1───N transactions

categories 1───N transactions
categories 1───N recurring_transactions
categories 1───N categories (subcategoria)

recurring_transactions 1───N transactions (geradas)

transactions N───1 transactions (mesmo purchase_group_id — agrupamento lógico,
                                   não é FK, é valor compartilhado)
```

Todas as FKs para tabelas com `user_id` devem, na camada de service, ser
validadas como pertencentes ao mesmo `user_id` da requisição (ex.: não deixar
criar uma transaction com `account_id` de outro usuário) — isso não é
garantido só pelo schema, é regra de negócio.

---

## 3. Autenticação

### 3.1 Dashboard web → JWT

Decisão: **JWT stateless**, não sessão de servidor.

Motivo: o Render free tier pode reiniciar/hibernar a instância (cold start),
o que tornaria sessões em memória inúteis sem um store externo (Redis, etc.)
— e isso seria complexidade extra desnecessária agora. JWT é stateless. Além
disso, a mesma API vai atender o bot no futuro, que não tem conceito de
"sessão de navegador" — um esquema de autenticação baseado em token
(Authorization header) serve os dois casos de forma mais uniforme do que
cookie de sessão.

Fluxo:
1. `POST /api/v1/auth/login` com email + senha → valida contra `password_hash`
   → retorna `access_token` (JWT, TTL curto, ex. 15-30min) e `refresh_token`
   (TTL longo, ex. 30 dias).
2. Cliente envia `Authorization: Bearer <access_token>` em toda requisição.
3. `POST /api/v1/auth/refresh` com o refresh token gera novo access token.
4. Payload do JWT contém `sub` (user_id) e `exp` — nada sensível além disso.

Biblioteca sugerida: `Flask-JWT-Extended` (madura, cobre access/refresh,
revogação por blocklist se necessário no futuro).

Refresh tokens ficam armazenados apenas no cliente (não precisam de tabela
própria na Fase 0); se no futuro for necessário revogar sessões
individualmente, isso vira uma tabela `refresh_tokens` — adiado por YAGNI.

### 3.2 Bot do WhatsApp → identificação por telefone

O bot não usa login/senha. O fluxo:

1. Meta Cloud API envia webhook com o número do remetente (`wa_id`, formato
   E.164, ex. `5511999999999`).
2. `bot` (camada fina, futura) recebe o webhook e chama a API interna
   autenticando-se com uma **credencial de serviço própria** (não é o usuário
   final) — ex. uma API key fixa do bot, guardada em variável de ambiente,
   diferente de qualquer JWT de usuário.
3. A rota da API usada pelo bot resolve o usuário fazendo
   `SELECT * FROM users WHERE phone_number = :wa_id`. Esse número é a chave de
   correspondência (por isso `users.phone_number` é `UNIQUE`).
4. Se não houver usuário com aquele número, a API responde indicando que o
   número não está vinculado — o bot pode então guiar um fluxo de
   "vincule seu número" (ex.: usuário cadastra o telefone dentro do dashboard
   web autenticado, depois de logado por JWT normalmente).

Ou seja: **dois mecanismos de auth coexistindo na mesma API**:
- Usuário final autenticado por JWT (dashboard).
- Serviço bot autenticado por API key própria + identificação indireta do
  usuário via `phone_number` (não é "autenticação do usuário", é resolução de
  identidade a partir de um canal já confiável — o número que enviou a
  mensagem ao WhatsApp Business).

Essa distinção importa: a API key do bot nunca deve ser tratada como
equivalente a "logado como qualquer usuário" — as rotas usadas pelo bot devem
ser explícitas sobre esperar `phone_number` e resolver o `user_id`
internamente, nunca aceitar um `user_id` arbitrário vindo do payload do bot.

---

## 4. Convenções de código

### 4.1 Tipagem

- Python 3.11+, type hints obrigatórios em toda função pública de `services/`
  e `api/` (parâmetros e retorno).
- Models SQLAlchemy usam `Mapped[...]` / `mapped_column(...)` (SQLAlchemy 2.0
  typed style), não o estilo legado `Column(...)` sem tipos.
- `mypy` rodando em modo não-estrito no início (permitir `Any` pontual), com
  meta de subir o rigor depois que o core estabilizar. Configurado em
  `pyproject.toml`.

### 4.2 Tratamento de erros

- Exceções de negócio custom em `app/services/exceptions.py` (a criar na
  Fase 1), ex.: `NotFoundError`, `ValidationError`, `ForbiddenError` —
  services levantam essas exceções, nunca retornam tuplas de erro nem chamam
  `abort()` diretamente (isso mantém services testáveis sem contexto Flask).
- `api/errors.py` registra error handlers globais (`@app.errorhandler`) que
  traduzem essas exceções para o formato de resposta padrão com o HTTP status
  correto (404, 422, 403, 500).
- Nunca deixar stack trace ou mensagem de exceção crua do SQLAlchemy vazar
  para o cliente — sempre logar internamente e responder mensagem genérica
  quando for erro 500.

### 4.3 Padrão de resposta da API

Sucesso:
```json
{
  "data": { ... },
  "meta": { }
}
```

Lista com paginação:
```json
{
  "data": [ ... ],
  "meta": { "page": 1, "per_page": 20, "total": 143 }
}
```

Erro:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "amount deve ser maior que zero",
    "details": { "field": "amount" }
  }
}
```

`code` é um identificador estável em `UPPER_SNAKE_CASE` (não muda com
i18n/reformulação da mensagem) — permite que `web` e `bot` tratem erros
programaticamente sem parsear texto.

---

## 5. Setup

### 5.1 Neon (PostgreSQL free tier)

1. Criar conta em neon.tech, criar um novo **Project** (ex. `financias-prod`).
2. Neon já cria um branch `main` e um database padrão — pode renomear o
   database para algo como `financias`.
3. Na aba **Connection Details**, copiar a *connection string* no formato
   pooled (`-pooler` no host) — importante usar a versão *pooled* porque o
   Render free tier + Flask com múltiplos workers se beneficia do PgBouncer
   do Neon em vez de abrir conexões diretas demais.
4. Guardar a string em `DATABASE_URL`. Formato:
   ```
   postgresql://<user>:<password>@<host>-pooler.<region>.aws.neon.tech/<db>?sslmode=require
   ```
5. Criar também um **branch de desenvolvimento** no Neon (ex. `dev`) — dá um
   banco isolado gratuito para testar migrations sem afetar dados reais.
   Nesse caso, `DATABASE_URL` local aponta para o branch `dev`.

### 5.2 Variáveis de ambiente

`.env.example` (nunca commitar `.env` real):

```
# Banco
DATABASE_URL=postgresql://user:password@host-pooler.region.aws.neon.tech/dbname?sslmode=require

# Flask
FLASK_ENV=development
SECRET_KEY=troque-por-uma-chave-aleatoria-longa

# JWT
JWT_SECRET_KEY=troque-por-outra-chave-aleatoria-longa
JWT_ACCESS_TOKEN_EXPIRES_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRES_DAYS=30

# Bot WhatsApp (futuro — placeholders desde já)
BOT_SERVICE_API_KEY=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
```

### 5.3 Deploy no Render (free tier)

1. Criar **Web Service** novo no Render, apontando para o repositório Git.
2. Runtime: Python 3.11+.
3. Build command: `pip install -r requirements.txt`.
4. Start command: `gunicorn wsgi:app` (ou `gunicorn "app:create_app()"` —
   ajustar conforme o entrypoint definido em `wsgi.py`).
5. Em **Environment**, cadastrar as mesmas variáveis do `.env.example` acima,
   com `DATABASE_URL` apontando para o branch `main` do Neon (produção).
6. Migrations: rodar `flask db upgrade` manualmente via *Render Shell* (ou
   como parte do build/deploy hook) após cada deploy que inclua migration
   nova — no free tier não há job/worker separado, então isso é feito no
   próprio deploy.
7. Observação sobre free tier do Render: a instância "dorme" após período de
   inatividade e tem cold start de alguns segundos no primeiro request —
   aceitável para uso pessoal na Fase 0, mas vale documentar para não causar
   susto se o dashboard demorar para responder após ociosidade.

---

## Resumo do que fica para depois (fora de escopo da Fase 0)

- Implementação de qualquer model, service, rota ou migration.
- Frontend do dashboard.
- Integração real com Meta Cloud API.
- Jobs agendados para geração de transações recorrentes (mecanismo definido
  conceitualmente na seção 2.10, implementação fica para quando `services` for
  criado).

---

## Riscos conhecidos

### Render free tier + webhook do WhatsApp (Meta Cloud API)

O Render free tier hiberna a instância após um período de inatividade e leva
alguns segundos para "acordar" no request seguinte (cold start — já citado na
seção 5.3). Isso é tolerável para o dashboard web (usuário só espera um pouco
mais), mas é um problema potencialmente mais sério para o webhook do
WhatsApp, que só será implementado na **Fase 4**:

- A Meta Cloud API espera que o endpoint de webhook responda rapidamente
  (dentro de poucos segundos). Se a instância estiver hibernada, o cold start
  pode causar **timeout** na entrega do webhook.
- Quando isso acontece, a Meta **reentrega a mesma mensagem** (retry
  automático) — o que pode gerar processamento duplicado de uma mensagem do
  usuário (ex.: lançar a mesma transação duas vezes) se o handler do webhook
  não for idempotente.

Esta arquitetura (Fase 0) não resolve esse problema agora — é uma decisão
adiada intencionalmente para a Fase 4, quando o bot for implementado. As
opções a avaliar nessa fase são, no mínimo:

1. **Upgrade do plano do Render** (sai do free tier, elimina a hibernação) —
   solução mais simples, tem custo mensal.
2. **Keep-alive** (ping periódico externo à própria instância, ex. via cron
   job gratuito) para evitar que ela hiberne — sem custo adicional, mas é uma
   solução frágil (ainda pode falhar em cold starts pontuais, e depende de um
   serviço de terceiros manter o ping funcionando).
3. Independentemente da opção acima, o handler do webhook deveria ser
   **idempotente** (ex. deduplicar pelo `message_id` que a Meta envia), como
   mitigação complementar ao problema de reentrega — isso é uma boa prática
   independente da causa raiz escolhida.

Nenhuma dessas opções está implementada nesta fase; esta seção existe apenas
para não perder essa decisão de vista até a Fase 4.

---

**Próximo passo:** aguardar aprovação para iniciar a Fase 1 (autenticação +
CRUD de receitas/despesas), que envolve criar de fato `models/user.py`,
`models/transaction.py`, `models/account.py`, `models/category.py`, a
primeira migration Alembic, e as rotas/serviços de auth + transactions.
