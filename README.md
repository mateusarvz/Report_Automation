# Report Psicologia

Um ambiente Python com front-end e back-end integrados em FastAPI, usando Supabase como banco de dados e login com Google OAuth.

## Instalação

1. Crie um ambiente virtual Python.
2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Crie um arquivo `.env` com base em `.env.example` e preencha os valores:

```bash
copy .env.example .env
```

4. Configure as variáveis com os dados do Supabase e do Google:
   - `SUPABASE_URL` ou `NEXT_PUBLIC_SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY` ou `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
   - `NEXT_PUBLIC_SITE_URL=http://localhost:8000`
   - `LOCAL_REDIRECT_TO=http://localhost:8000/auth/callback`
   - No Render, defina `NEXT_PUBLIC_SITE_URL=https://report-automation-tcht.onrender.com`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REDIRECT_URI=https://xhfhojoyphdfozqqhxsg.supabase.co/auth/v1/callback`
   - `SESSION_SECRET_KEY`

5. Configure o redirect URI no Google Cloud Console para `https://xhfhojoyphdfozqqhxsg.supabase.co/auth/v1/callback`.

6. No dashboard Supabase, configure as Redirect URLs do Auth para incluir:
   - `http://localhost:8000/auth/callback`
   - `https://xhfhojoyphdfozqqhxsg.supabase.co/auth/v1/callback`

> Se você usar a chave pública (`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`), certifique-se de que a tabela `profiles` permita inserts e selects para essa chave no Supabase.

## Executar

```bash
uvicorn main:app --reload
```

Abra `http://localhost:8000` no navegador.

## O que o site faz

- Conecta ao Supabase usando `DATABASE_URL`
- Autentica usuários com Google
- Após login, redireciona para a home
- Exibe uma barra lateral com "Dados da conta" e "Dados dos Pacientes"
- Mostra os dados do email do usuário na seção de conta
- Mantém "Dados dos Pacientes" vazia por enquanto
