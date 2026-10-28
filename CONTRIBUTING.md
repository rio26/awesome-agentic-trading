# Contributing

Thanks for helping keep this list useful. The bar is deliberately high: a short list people trust beats a long one they skim.

## Inclusion criteria

An entry must meet all of these:

1. **Open source, or a primary source.** Code entries need a public repository with a recognised license. Non-code entries (papers, incidents, regulation) need a primary source: the paper itself, the regulator's page, the operator's own postmortem or a reputable news report.
2. **It runs, or it happened.** Code entries must be installable and runnable from their README today. Vapourware, waitlists and "coming soon" are not listed.
3. **An agent angle.** The project must involve an LLM or autonomous agent in the decision loop, or be a tool built specifically to feed, execute for, constrain or evaluate such agents. A broker SDK qualifies only if agents commonly use it (ccxt, Alpaca); a generic charting library does not.
4. **Honest about mode.** Every code entry carries a `mode`: `live` (places real orders), `paper` (simulated orders only), `research` (backtests and studies), or `library` (building block). A `live` project must document its risk controls, or it goes in as `paper` with a note.
5. **No signal-selling.** No paid signal groups, copy-trading funnels, token launches, "guaranteed returns", or projects whose README is mostly a Telegram link.
6. **Activity.** Code entries should have a commit in the last six months, or be foundational enough that staleness does not matter (we say so in the description).

The weekly job marks entries that go quiet; maintainers remove them after a further six months or when the project is archived.

## How to add an entry

1. Add it to [`data/entries.yaml`](data/entries.yaml). Fields:

   ```yaml
   - name: Project Name
     repo: owner/name            # GitHub repos; use `url:` for anything else
     section: agents             # a key from data/sections.yaml
     description: One factual sentence ending with a full stop. No marketing, no emojis.
     markets: [equities, crypto] # equities, crypto, futures, options, forex, prediction-markets, multi-asset
     mode: paper                 # live, paper, research, library
     language: Python
     added: 2026-10-28
   ```

2. Run `python scripts/build_readme.py` (needs `pip install -r requirements.txt`) and commit both the YAML and the regenerated `README.md`. CI fails if they disagree.
3. One entry per pull request, with a sentence on why it belongs. If you are the author, say so.

## Style for descriptions

Write what the project does, not how great it is. "Multi-agent LLM framework that produces daily long/short decisions for US equities from news and fundamentals" is a description. "Revolutionary AI trading platform" is not. Keep it under 260 characters.

## Reporting a problem

Open an issue if a listed project has stopped working, turned into a paid product, or did something the community should know about (lost user funds, prompt-injection incident, undisclosed live trading). Incidents with a source go into the Incidents section; that section is part of the point of this list.
