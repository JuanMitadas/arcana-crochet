# External accounts and business registration

Suggested order: sandboxes first (free, they unblock development), business registration in parallel, production accounts only close to launch.

## 1. Business registration (MEI)

Crochet qualifies for MEI: the occupation is **crocheteiro(a) independente**, CNAE 1422-3/00. In 2026 the monthly DAS is around R$ 82 and the revenue limit is R$ 81,000 a year.

1. Create or recover your **gov.br** account (silver or gold level).
2. Open the MEI on the Portal do Empreendedor, choosing the occupation above.
3. Before selling, take these questions to an accountant:
   - Does the activity require an **Inscrição Estadual** in SP? (it's an industrial activity and pays ICMS in the DAS)
   - Do shipments through Correios/carriers need an **NF-e**, or can I use a declaração de conteúdo? Melhor Envio only accepts the declaration for individuals and companies that are **not** ICMS taxpayers.
   - How do I issue an NF-e when needed (SEFAZ's free issuer or an ERP)?
   - Can the site, under the MEI's name, have a domain and business accounts at Asaas and Melhor Envio without issues?

## 2. Asaas — sandbox (payments)

1. Create an account at **https://sandbox.asaas.com** (it's separate from the real account; test data is fine).
2. In the menu, open **Integrações** and generate the **API key**. It's shown **only once**: copy it right away.
3. In `.env`, fill in:
   ```
   ASAAS_BASE_URL=https://sandbox.asaas.com/api/v3
   ASAAS_API_KEY=<the copied key>
   ```
4. The key goes in the `access_token` header of each request, along with `User-Agent` (the project's integration will do this).
5. Webhook: only in the checkout phase. It needs a public URL: the site already published on AWS (the CloudFront address or the custom domain).

Docs: https://docs.asaas.com (Sandbox, Cobranças, Pix, Webhooks).

## 3. Melhor Envio — sandbox (shipping)

1. Create an account at **https://sandbox.melhorenvio.com.br**. The sandbox starts with R$ 10,000 of fake balance for test labels.
2. Register the store's origin address (where the pieces ship from).
3. Generate an access token in the dashboard (**Integrações** → access tokens/permissions). For a single store, the account's personal token is enough; the OAuth app flow (Integrações → Área Dev → Cadastrar aplicativo) is only needed if other accounts were to use the system.
4. In `.env`, fill in:
   ```
   MELHOR_ENVIO_BASE_URL=https://sandbox.melhorenvio.com.br
   MELHOR_ENVIO_TOKEN=<the token>
   MELHOR_ENVIO_USER_AGENT=Arcana Crochet (your-email@example.com)
   ```
5. Every request needs the `User-Agent` header in the `App name (email)` format.

Docs: https://docs.melhorenvio.com.br

## 4. AWS and domain

The complete walkthrough (AWS account, secrets, deploy through GitHub, database and custom domain) is in [deploy.md](deploy.md). The database (Aurora DSQL) is created by the stack itself: there is no external database account.

Domain: register the `.com.br` at **Registro.br** (requires a CPF or CNPJ). You can publish and test before that on the `*.cloudfront.net` address.

## 5. Transactional email

Without email configured, nobody can sign up on the published store (sign-up requires confirming the email). Create an account at **Resend** or **Brevo**, verify the domain (they show the SPF/DKIM records to paste into the DNS) and store the SMTP credential in the `EMAIL_URL` parameter with `infra/configurar-segredos.sh`:

```
EMAIL_URL=smtp+tls://<user>:<password-or-api-key>@<smtp-server>:587
```

## 6. Sign in with Google

The "Continuar com o Google" button appears on the login, sign-up and checkout pages once the Google credentials are set. It only asks Google for the name and email; the person's Google tokens are not stored.

1. Open https://console.cloud.google.com with the store's Google account and create a project called `Arcana Crochet`.
2. **APIs & Services → OAuth consent screen** (Google Auth Platform → Branding): app name *Arcana Crochet*, support email, the store logo and the site address. Audience: **External**. A privacy policy page is required before publishing (step 5); the store doesn't have one yet.
3. **Clients → Create client** → *Web application*:
   - **Authorized JavaScript origins:** `https://d2ab108d7u9pzi.cloudfront.net` (later also `https://arcanacrochet.com.br`).
   - **Authorized redirect URIs:** `https://d2ab108d7u9pzi.cloudfront.net/conta/google/login/callback/` (later also `https://arcanacrochet.com.br/conta/google/login/callback/`).
   - For local tests, add `http://localhost:8000` and `http://localhost:8000/conta/google/login/callback/`.
4. Copy the **Client ID** and **Client secret** and store them with `bash infra/configurar-segredos.sh` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`), then run the deploy again. For local tests, put them in `.env`.
5. While the app is in **Testing**, only the Google accounts listed under *Audience → Test users* can sign in. Before launch, click **Publish app**: with only name and email (no sensitive scopes) Google doesn't require a review, but it does ask for the custom domain in *Authorized domains*, so do this once `arcanacrochet.com.br` is set up.

Someone who already has an account with the same email signs in to that account with Google (Google confirms the email). New people get an account created with their Google name and email, already verified.

## 7. Production accounts (close to launch)

With the CNPJ in hand: a **business** account at Asaas (`https://api.asaas.com/v3`) and at Melhor Envio (`https://melhorenvio.com.br`), with balance for labels. Change the URLs and keys in the SSM parameters (`/arcana/prod/`). Never use a production key in your computer's `.env`.
