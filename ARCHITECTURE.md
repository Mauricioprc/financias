# ARCHITECTURE.md

Sistema de gestão financeira pessoal — Fase 0 (fundação).

Stack: Flask + SQLite + SQLAlchemy + Alembic. Backend hospedado no
PythonAnywhere (free tier) — ver seção 5.1 para o racional da escolha de banco.
Duas interfaces futuras (dashboard web, chatbot WhatsApp via Meta Cloud API)
consumindo a mesma API e o mesmo banco.

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
├── wsgi.py                     # entrypoint WSGI (usado pelo arquivo de config do PythonAnywhere)
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

Motivo: sessão em memória de servidor exigiria um store externo (Redis etc.)
para sobreviver a restart do processo — complexidade extra desnecessária
agora. JWT é stateless. Além disso, a mesma API vai atender o bot no futuro,
que não tem conceito de "sessão de navegador" — um esquema de autenticação
baseado em token (Authorization header) serve os dois casos de forma mais
uniforme do que cookie de sessão.

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

### 5.1 Banco de dados: SQLite local

Decisão revista após a Fase 0 (era Neon/Postgres inicialmente — ver histórico
do Git para o racional anterior). O app roda em SQLite, um arquivo local em
`instance/financias.db` (pasta já no `.gitignore`), pelos seguintes motivos:

- Viabiliza hospedagem no **free tier do PythonAnywhere**, que restringe
  saída de rede a uma allowlist de domínios — bancos externos como Neon não
  estão nela, então uma conexão de rede pra Postgres gerenciado simplesmente
  não abre nesse plano. SQLite é um arquivo, não abre conexão de rede
  nenhuma, então não esbarra nessa restrição.
- Escala do projeto (uso pessoal/familiar) não justifica um Postgres
  gerenciado — SQLite aguenta tranquilamente esse volume de dados/escrita.
- `SQLALCHEMY_DATABASE_URI` já é lido de `DATABASE_URL` via variável de
  ambiente (`app/config.py`), então trocar de engine é só trocar o valor da
  URL — nenhum código muda. Todas as migrations em `migrations/versions/`
  usam `batch_alter_table`, que é compatível com SQLite (Postgres também).

Formato da URL (caminho **absoluto** — SQLite exige isso):
```
sqlite:////caminho/absoluto/para/instance/financias.db
```
(repare nas 4 barras: três do esquema `sqlite://` + a barra inicial do
caminho absoluto)

Se no futuro o volume de dados ou a necessidade de acesso concorrente
justificar voltar a um banco gerenciado, a troca é só de novo mudar
`DATABASE_URL` — nenhuma migration ou service precisa ser reescrito.

### 5.2 Variáveis de ambiente

`.env.example` (nunca commitar `.env` real):

```
# Banco
DATABASE_URL=sqlite:///instance/financias.db

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

### 5.3 Deploy no PythonAnywhere (free tier)

1. Criar conta em pythonanywhere.com (plano **Beginner/free**).
2. Fazer upload do repositório — via `git clone` no **Bash console** deles
   (têm git instalado) apontando pro repo no GitHub.
3. Criar um virtualenv e instalar `requirements.txt` (`mkvirtualenv` ou
   `python -m venv`, conforme preferência).
4. Na aba **Web**, criar uma nova web app, framework "Manual configuration"
   (não usar o wizard de Flask deles, já temos `wsgi.py` pronto), Python
   3.11+.
5. Editar o arquivo de configuração WSGI que o PythonAnywhere gera, apontando
   pro nosso `create_app()`:
   ```python
   import sys
   path = "/home/<usuario>/financias"
   if path not in sys.path:
       sys.path.insert(0, path)

   from app import create_app
   application = create_app("production")
   ```
6. Configurar `DATABASE_URL` e as demais variáveis de `.env.example` — o
   PythonAnywhere não lê `.env` automaticamente fora do Bash console, então
   ou se define via `os.environ` no próprio arquivo WSGI acima (antes do
   `create_app()`), ou se garante que `python-dotenv` carrega o `.env` que
   foi enviado junto (mais simples: exportar direto no WSGI file mesmo,
   já que ele não é servido publicamente).
7. Apontar o **Static files mapping** da aba Web pra pasta `static/` do
   projeto (opcional — Flask já serve os estáticos, mas o PythonAnywhere
   serve mais rápido direto por fora do WSGI).
8. Migrations: `flask --app wsgi:app db upgrade` no Bash console, sempre que
   uma migration nova entrar.
9. Sem cold start nesse plano (diferente do Render free tier) — a única
   limitação real do free tier é a allowlist de saída de rede (não afeta o
   dashboard, que só fala com o próprio banco local; passa a importar quando
   o bot do WhatsApp existir — `graph.facebook.com` já está na allowlist
   deles, então a Fase 4 deve funcionar sem upgrade de plano, mas vale
   confirmar no momento).

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

### Allowlist de rede do PythonAnywhere free tier + webhook do WhatsApp (Meta Cloud API)

Diferente do Render, o PythonAnywhere free tier não hiberna a instância — não
há cold start a se preocupar para o dashboard nem para o webhook. O risco
real desse plano é outro: **saída de rede é restrita a uma allowlist de
domínios**. Bancos externos como Neon não estavam nela (motivo da migração
para SQLite, seção 5.1); `graph.facebook.com` (usado pela Meta Cloud API do
WhatsApp) **está** na allowlist, então o bot (Fase 4) deve funcionar sem
upgrade de plano — mas vale confirmar isso na prática antes de depender
disso, já que a lista pode mudar.

Mesmo sem risco de cold start, **idempotência no handler do webhook continua
sendo boa prática** — a Meta pode reentregar uma mensagem por outros motivos
(timeout de rede pontual, erro 5xx transitório), e sem deduplicar pelo
`message_id` isso geraria processamento duplicado (ex.: lançar a mesma
transação duas vezes). Fica mantido como parte do design da Fase 4.

Se no futuro a allowlist bloquear algo necessário, as opções são: upgrade
para o plano pago do PythonAnywhere (remove a restrição de rede) ou migrar a
hospedagem — nenhuma decisão precisa ser tomada agora.

---

**Próximo passo:** aguardar aprovação para iniciar a Fase 1 (autenticação +
CRUD de receitas/despesas), que envolve criar de fato `models/user.py`,
`models/transaction.py`, `models/account.py`, `models/category.py`, a
primeira migration Alembic, e as rotas/serviços de auth + transactions.
