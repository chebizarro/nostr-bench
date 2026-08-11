# Publishing nostr-bench

This repo is set up to live in two places at once: **GitHub** (for reach and CI)
and **Nostr** (for sovereignty — code collaboration over relays, no platform
lock-in, via [NIP-34](https://nips.nostr.com/34)).

## Prerequisites

```bash
# clean state — never commit results, keys, or node_modules
git status                       # should show only source files
cat .gitignore                   # runs/, .nmcache/, node_modules/, *.env, .orkey
```

Make sure no API key, `.orkey`, `or_models.json`, `runs/`, or `.nmcache/`
directories are staged. They're all in `.gitignore`; double-check before the
first push.

## GitHub

```bash
git init                         # if not already a repo
git add -A
git commit -m "nostr-bench: open-weight model harness for nostr + security"

gh repo create chebizarro/nostr-bench --public --source=. --remote=origin --push
# or, manually:
#   git remote add origin git@github.com:chebizarro/nostr-bench.git
#   git branch -M main
#   git push -u origin main
```

CI (`.github/workflows/ci.yml`) runs the wiring self-check and verifies the
bundled reference solutions still pass the hidden suites on every push — no API
keys needed, so it's safe on a public fork.

## Nostr (NIP-34, via ngit)

[`ngit`](https://ngit.dev) turns any git repo into a nostr-native one: it
publishes a repository announcement (kind `30617`) to your relays, and pushes
commits as nostr events so anyone can clone, patch, and PR over relays instead
of through a platform.

```bash
# one-time: install ngit (see https://ngit.dev / codeberg.org/DanConwayDev/ngit-cli)
#   cargo install ngit         # or download a release binary

# from inside the repo, after your GitHub push:
ngit init
#   → prompts for: repo name/description, your maintainer npub,
#     relays to announce on, and (optionally) a GRASP server to host the git data
#     (https://ngit.dev/grasp/). It writes a maintainers.yaml and announces the repo.

git push                         # ngit installs a nostr remote helper; pushes go to relays
```

Contributors then `ngit clone naddr1...` and send patches with `ngit send`;
you review incoming proposals with `ngit list`. If you run a
[GRASP](https://ngit.dev/grasp/) server (or use your `grasp-gitea` setup), point
`ngit init` at it so the actual git objects live on a host you control while the
coordination happens over nostr.

## Announcing the results

The companion write-up (`docs/bring-your-own-protocol.md`) is the human-facing
artifact — publish it as a long-form note (NIP-23, kind `30023`) and link the
repo's `naddr` so readers can clone the harness and run it against their own
protocol. The dashboard (`report/results.html`) is a self-contained file; host
it anywhere or drop it in a Blossom/relay-backed static host.

> Keep the keys off the wire. `nostr-bench` never needs your `nsec`; ngit signs
> with your nostr identity locally. The only secret the harness itself uses is an
> OpenRouter key, passed by environment variable and never written to the repo.
