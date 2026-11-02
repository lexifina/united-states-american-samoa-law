# strategy/

`STRATEGY-LOG.md` is the decision record for the global-law coverage push: what was decided, who did it, and the measured effect.

`census-<date>.tsv` lists every lexifina/*-law repo with four tab-separated columns: size_kb, private, pushed_at, name.

Re-run the census with:

```sh
gh api --paginate "orgs/lexifina/repos?per_page=100&type=all" \
  --jq '.[] | select(.name|endswith("-law")) | "\(.size)\t\(.private)\t\(.pushed_at[0:16])\t\(.name)"' > strategy/census-$(date -u +%F-%H%M).tsv
```
