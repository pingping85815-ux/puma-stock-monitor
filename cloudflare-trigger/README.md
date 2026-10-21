# Cloudflare scheduler

This free Worker triggers the existing GitHub Actions workflow every five
minutes. The Python monitor, Gmail secrets, and persistent `state` branch remain
in GitHub.

## Deploy

1. Create a fine-grained GitHub token limited to
   `pingping85815-ux/puma-stock-monitor`, with only **Actions: Read and write**.
2. Install Wrangler and authenticate:
   `npm install --global wrangler`
   `wrangler login`
3. From this directory, save the token and deploy:
   `wrangler secret put GITHUB_TOKEN`
   `wrangler deploy`

Do not put the token in this repository or in `wrangler.toml`.
