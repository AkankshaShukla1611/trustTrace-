# Sample report

`covenace_candidate_run_report.{md,json}` is a real report pulled from a
real run (`GET /runs/{run_id}/report`), not a hand-written mockup -- the
run is the CovenAce pack's "Output Year memo" candidate run described in
`backend/app/evaluation_packs/covenace_pack/README.md`. Regenerate it
yourself at any time:

```bash
curl "http://127.0.0.1:8731/runs/<run_id>/report?format=markdown"
curl "http://127.0.0.1:8731/runs/<run_id>/report?format=json"
```
