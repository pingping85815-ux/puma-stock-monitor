# PUMA Stock Monitor

A small, dependency-free PUMA UK stock monitor that runs in GitHub Actions and
sends an email when a product changes from out of stock to in stock. After
setup, GitHub runs it in the cloud; Codex and your computer do not need to stay
online.

The monitor reads the product's schema.org `Product`/`Offer` JSON-LD and uses
visible page text only as a fallback. Failed or inconclusive checks stop the
workflow and never generate a restock alert.

## How it avoids duplicate alerts

The workflow stores only `InStock` or `OutOfStock` in a dedicated `state`
branch. It sends mail only when the saved value is not `InStock` and the new
value is `InStock`. Runs are serialized, state is updated only after a required
email succeeds, and unchanged states are not written again. No credentials are
stored in the state branch.

GitHub Actions schedules are best-effort: a run can start late during busy
periods. Public repositories may also have scheduled workflows disabled after
60 days without repository activity.

## 1. Fork the project

1. Sign in to GitHub and open this repository.
2. Select **Fork** and create the fork in your own account.
3. In your fork, open **Settings → Actions → General**.
4. Under **Workflow permissions**, choose **Read and write permissions**, then
   save. This lets the workflow maintain the non-sensitive `state` branch.

## 2. Choose the product

The included PUMA product remains the default. To monitor another PUMA UK
product, open **Settings → Secrets and variables → Actions → Variables**, add a
repository variable named `PRODUCT_URL`, and paste the complete product URL.

## 3. Configure email secrets

Open **Settings → Secrets and variables → Actions → Secrets** and create these
repository secrets:

| Secret | Required | Example / meaning |
| --- | --- | --- |
| `RECIPIENT_EMAIL` | Yes | Address that receives alerts |
| `SMTP_USER` | Yes | Mailbox used to send alerts |
| `SMTP_PASSWORD` | Yes | App password or SMTP authorization key, not your normal password |
| `SMTP_HOST` | No | Defaults to `smtp.gmail.com` |
| `SMTP_PORT` | No | Defaults to `465` |
| `SMTP_SSL` | No | Defaults to `true`; use `false` for STARTTLS, commonly on port `587` |

For Gmail, enable two-step verification and create a Google App Password. Use
that 16-character app password as `SMTP_PASSWORD`. Never put a real address,
password, token, or authorization key in the repository, workflow file, issue,
or Actions log.

Other mail providers can be used by setting their SMTP host, port, SSL mode,
username, and authorization key. Some providers require the sender address to
match `SMTP_USER`.

## 4. Enable and test GitHub Actions

1. Open the **Actions** tab in your fork.
2. If GitHub displays a warning for forked workflows, select **I understand my
   workflows, go ahead and enable them**.
3. Select **PUMA stock monitor → Run workflow**.
4. Enable **Send an SMTP test email before checking stock**.
5. Select **Run workflow** and wait for a green check mark.
6. Confirm that the test email arrived.

The first successful stock check creates the `state` branch. If the product is
already in stock on that first check, one alert is sent. Later checks do not
repeat it while the product remains in stock.

## 5. Change the monitoring frequency

Edit `.github/workflows/stock-monitor.yml` in your fork and change the `cron`
line under `schedule`. GitHub uses UTC and supports a minimum scheduled interval
of five minutes.

Examples:

```yaml
# Every 5 minutes, offset from busy round-number times
- cron: "2-59/5 * * * *"

# Every 15 minutes
- cron: "7-59/15 * * * *"

# Once per hour
- cron: "17 * * * *"
```

Manual **Run workflow** checks remain available regardless of the schedule.

## Troubleshooting

### The test email fails

- Confirm all three required secrets exist and their names match exactly.
- For Gmail, use an App Password rather than your normal account password.
- Check whether your provider expects SSL on port 465 or STARTTLS on port 587.
- Open the failed Actions run and inspect the failing step. GitHub masks secret
  values, but do not copy secrets into logs while debugging.

### The scheduled workflow does not run exactly on time

GitHub may delay scheduled jobs, especially near common clock boundaries. This
workflow intentionally uses an offset schedule. Scheduled workflows in inactive
public repositories may be disabled after 60 days; re-enable them in Actions.

### The stock check fails

PUMA may temporarily reject or rate-limit a request, or its page structure may
change. A failed check exits without sending a restock email and leaves the
saved state unchanged, so a later successful run can try again safely.

### Persisting the state fails

Confirm **Read and write permissions** is enabled under **Settings → Actions →
General** and that repository rules do not block the `state` branch. The
workflow retries transient GitHub push failures three times.

### I changed products and received an immediate alert

Delete the `state` branch before the first run for the new product, or accept
the single initial alert if the new product is already available.

## Optional local use

Local use is not required for GitHub Actions. If desired:

```bash
cp .env.example .env
python3 monitor.py --test-email
python3 monitor.py --once
```

The ignored `.env` file holds local settings, `state.json` holds local stock
state, and `monitor.log` holds local logs. None should be committed.

## Security and privacy

- Runtime code uses only the Python standard library; `requirements.txt` is
  intentionally empty of third-party packages.
- Secrets are read from GitHub Actions Secrets or a local ignored `.env` file.
- The repository contains no personal email address, password, token, machine
  path, or local log.
- The workflow prints stock status and product metadata, never SMTP credentials.

## License

See [LICENSE](LICENSE).
