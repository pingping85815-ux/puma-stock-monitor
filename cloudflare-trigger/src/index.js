const DISPATCH_URL =
  "https://api.github.com/repos/pingping85815-ux/puma-stock-monitor/actions/workflows/stock-monitor.yml/dispatches";

async function dispatch(env) {
  const response = await fetch(DISPATCH_URL, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "puma-stock-monitor-trigger",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: { send_test_email: "false" },
    }),
  });

  if (response.status !== 204) {
    throw new Error(`GitHub dispatch failed: HTTP ${response.status}`);
  }
}

export default {
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(dispatch(env));
  },

  async fetch() {
    return new Response("PUMA stock monitor trigger is active.\n");
  },
};
