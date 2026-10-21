# PUMA stock monitor

A small, dependency-free Python monitor for this PUMA UK product:

- Product: Scuderia Ferrari Replica Singapore Charles Leclerc Baseball Cap
- SKU: `4070034024903`
- URL size parameter: `0150`

It reads PUMA's server-rendered schema.org JSON-LD
`offers.availability` value. Gmail SMTP mail is sent only when the saved state
is not `InStock` and the new state is `InStock`. This includes the first cloud
check when the product is already available.

The monitoring-loop/state approach is adapted from common public stock-monitor
projects such as
[`nearyou/pokemon-stock-monitor`](https://github.com/nearyou/pokemon-stock-monitor),
with original PUMA-specific parsing, SMTP and GitHub Actions state handling.

## GitHub Actions cloud deployment

The workflow at `.github/workflows/stock-monitor.yml`:

- runs on the standard `ubuntu-latest` runner;
- checks every five minutes and can also be started with **Run workflow**;
- has no pip dependencies, browser download, cache or artifact storage;
- stores the last non-sensitive stock state in the repository Actions variable
  `PUMA_STOCK_STATE`;
- serializes runs so two checks cannot race and send duplicate mail;
- updates the state only after a required restock email succeeds.

### Required Actions secrets

In the GitHub repository, open **Settings → Secrets and variables → Actions →
Secrets → New repository secret** and add:

| Secret | Gmail value |
| --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_SSL` | `true` |
| `SMTP_USER` | Gmail address used to send mail |
| `SMTP_PASSWORD` | 16-character Google App Password, not the normal password |
| `EMAIL_FROM` | Usually the same Gmail address |
| `EMAIL_TO` | Destination email address |

Never commit `.env`. The repository `.gitignore` excludes `.env` and all local
variants except the placeholder-only `.env.example`.

### First cloud test

1. Open **Actions → PUMA stock monitor**.
2. Select **Run workflow**.
3. Enable **Send a Gmail SMTP test email before checking stock**.
4. Run it and confirm every step is green.
5. Confirm the test email arrives.
6. Under **Settings → Secrets and variables → Actions → Variables**, confirm
   `PUMA_STOCK_STATE` was created with `OutOfStock` or `InStock`.

Keep the local monitor running until this test succeeds. Afterwards the local
schedule can be disabled to prevent two independent monitors from sending at
the same time.

## Local use

```bash
cp .env.example .env
python3 monitor.py --test-email
python3 monitor.py --once
python3 monitor.py
```

Local state is stored in the ignored `state.json`. Local credentials remain in
the ignored `.env`.

## Operational notes

- GitHub documents five minutes as the shortest Actions schedule interval, but
  scheduled jobs can be delayed or occasionally dropped during high load.
- In a public repository, GitHub may disable scheduled workflows after 60 days
  with no repository activity; re-enable the workflow from the Actions page.
- This project uses only standard public-repository runners and does not select
  larger runners or any paid service.
