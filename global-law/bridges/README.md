# Bridges between legal systems

Finds provisions in different jurisdictions that do the same legal job, and writes them as typed edges
(`relation`, `concept`, `family`, `note`, `sim`, plus each side's amendment dates). It reads the four corpus
checkouts in `~/Documents` (grundgesetz, swiss-law, uk-law-history, us-code-history).

Run from a working folder (outputs are gitignored here), in this order:

1. `python extract.py kg.json`: amending laws and cross-references per corpus.
2. `python build_corpus.py`: `provisions.jsonl`, one record per provision (repealed stubs dropped).
3. `python constitute_parse.py`: Constitute topic tags for the German and Swiss constitutions. Download
   `constitute/topics.json` and `constitute/{German_Federal_Republic_2014,Switzerland_2014}.html` first from
   `https://www.constituteproject.org/service/topics?lang=en` and `.../service/html?cons_id=<id>&lang=en`.
4. `embed_in_container.py` inside the backend container (`text-embedding-3-large`): `emb.npy`. Pipe files in
   and out with `docker compose exec -T backend sh -c 'cat > ...'`, because `docker cp` fails on this machine,
   and set `MSYS_NO_PATHCONV=1` in Git Bash.
5. `python analyze.py`: evaluation against both answer keys, and mutual-nearest-neighbour candidates.
6. `python make_jobs.py`, then `llm_in_container.py` (gpt-5.4-mini on the US East 2 deployment): reranking,
   judging and cluster names.
7. `python score.py`: `report.json` and `bridges.json`. A family-classification call (`results2.jsonl`) and
   `page_data.py` feed the Legal System Bridges page.

`python query.py "de|Art. 4"` or `python query.py setoff` prints the bridges for a provision or a concept.

Results on 2026-10-28: 426 candidates, of which 308 were kept (22 equivalent, 86 analogous, 200 related).
Top-1 accuracy on the hand key rose from 47% with embeddings alone to 69% with a model rerank. On Constitute
tags it rose from 41% to 44%.

`gold_hand.json` is the hand-written answer key.
