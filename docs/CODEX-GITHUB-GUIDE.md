# Beginner Guide: Codex, Docker, and GitHub

This guide uses three tools:

| Tool | What it does |
| --- | --- |
| Docker Desktop | Runs Odoo, n8n, and the databases on your computer |
| GitHub Desktop | Publishes the project and keeps a clear change history |
| Codex in the ChatGPT desktop app | Explains, edits, checks, commits, and later pushes project changes |

Use a **private** GitHub repository. GitHub stores the project instructions and
code; it must not store passwords, email credentials, databases, backups, or
real prospect data.

## Stage 1 — Prepare the computer

Install these applications from their official sites:

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. [GitHub Desktop](https://desktop.github.com/)
3. [ChatGPT desktop](https://openai.com/chatgpt/desktop/)

Create a GitHub account if you do not already have one. Sign in to GitHub
Desktop, then start Docker Desktop and wait until it reports that Docker is
running.

Do not install Odoo, n8n, or PostgreSQL separately. Docker starts the versions
defined in this project.

## Stage 2 — Put the project in GitHub

1. Extract `GGD-Sales-System-Starter-Kit.zip`.
2. In GitHub Desktop choose **File → Add local repository**.
3. Select the extracted `ggd-sales-system` folder.
4. The repository has no first commit yet. In the bottom-left summary box enter:
   `Initial GGD sales system`.
5. Click **Commit to main**.
6. Click **Publish repository**.
7. Repository name: `ggd-sales-system`.
8. Keep **Private repository** selected, then publish.

Before committing, GitHub Desktop should not show `.env`, database files, or
backup contents. The project already ignores those items. If any appear, stop
and ask Codex to check the Git ignore rules.

## Stage 3 — Open the project in Codex

1. Open the ChatGPT desktop app.
2. Select **Codex**.
3. Choose **Open folder** and select `ggd-sales-system`.
4. Send this first prompt:

```text
Read AGENTS.md, PLAN.md, and README.md. Explain the current project status in
simple language. Do not change files and do not start Docker.
```

Then send:

```text
Check only whether Docker and Docker Compose are installed and running. Explain
any problem step by step. Do not change project files or start the services.
```

Codex should follow `AGENTS.md`, keep each stage small, and protect secrets.

## Stage 4 — Start the local system

After Docker is confirmed healthy, send Codex this prompt:

```text
Read AGENTS.md. Run the project validation, then run the local setup script.
Explain each important result in simple language. Never display values from
.env. Do not connect email, add an LLM key, or send messages.
```

Codex will use:

```bash
./scripts/validate-project.sh
./scripts/setup-local.sh
```

When startup finishes:

- Odoo should open at `http://localhost:8069`.
- n8n should open at `http://localhost:5678`.

If an error appears, copy only the error text to Codex. Never paste `.env`, a
password, API key, access token, or full email credential into chat.

## Stage 5 — Configure Odoo first

Complete Odoo before connecting email or an LLM:

1. Create the Odoo database as described in `README.md`.
2. Install CRM.
3. Install **Germany Growth Desk CRM Controls**.
4. Create the pipeline in `docs/ODOO-SETUP.md`.
5. Create one fictional lead and run all six control tests.

Use this Codex prompt:

```text
Guide me through docs/ODOO-SETUP.md one step at a time. Wait for my confirmation
after every numbered step. Use a fictional company only. Do not connect email.
```

## Stage 6 — Add n8n workflows safely

Build one workflow at a time in this order:

1. lead qualification;
2. draft creation;
3. approval-gated test send to your own address;
4. reply analysis;
5. daily follow-up review queue.

Use the specification in `docs/N8N-AUTOMATION-SPEC.md`. Add Zoho and LLM secrets
only in n8n's **Credentials** screen. Do not put them in workflow JSON or GitHub.

Suggested prompt for each workflow:

```text
Read AGENTS.md and docs/N8N-AUTOMATION-SPEC.md. Help me build Workflow 1 only.
Give me one n8n click at a time and wait for confirmation. Use fictional test
data, do not activate the workflow, and do not send email.
```

Change `Workflow 1` to the next workflow only after the current one passes.

## Stage 7 — Save future changes to GitHub

After Codex changes files, ask:

```text
Review all current changes. Run ./scripts/validate-project.sh. Explain the diff
in simple language and check that no secret or real customer data is included.
Do not commit until I confirm.
```

After reviewing the result, tell Codex:

```text
Commit the reviewed changes with a clear message and push the main branch to
GitHub. Do not include .env, backups, credentials, or customer data.
```

You can also commit and push with GitHub Desktop. The **Changes** tab is the
safest place to review exactly what will be published.

## What must never be pushed

- `.env`
- passwords, access tokens, API keys, and n8n credential exports
- Odoo or n8n database data
- backup archives
- real email bodies or prospect lists
- logs containing personal or confidential data

If GitHub reports a failed check, open the repository's **Actions** tab, open
the failed run, and give Codex the error text. Do not copy unrelated secrets or
customer information with it.

## Recommended working rhythm

1. Ask Codex for one small change.
2. Let Codex validate it.
3. Review the change in GitHub Desktop.
4. Commit with a clear message.
5. Push to the private GitHub repository.
6. Test locally with fictional data.
7. Back up before every major Odoo or n8n change.
