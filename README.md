# Household-command prompt cup

A web page that runs [needle 3](https://huggingface.co/Cactus-Compute/needle3), a small tool-calling model, inside
your own browser tab and scores a system prompt on the 196 household commands of the Home LLM Leaderboard's
assist-mini home. Nothing leaves the tab once the page and the model are downloaded.

## What the eleven scores show

On these 49 household commands (each run four times, so 196), across the eight authored prompts tried, needle 3's
result moved by at most three commands. On the leaderboard, Home Assistant's own prompt lands the same 12 in all three
of its runs; against it, six of the eight authored prompts move one command up or one down, and two move three. A
one-command lead can flip on the date line and the order of the tools, bytes a prompt's author does not write.
Replayed in its own recorded run, P10 lands 16, as on the leaderboard; typed into the page, which uses the default
prompt's recorded run, it lands 12. RESULTS.md prints, beside each prompt's 196-command score, how many commands it
moved up and down against plain-1. That column counts the page's own landed commands, not the leaderboard's, so it
can read one command away from the moves above: P7 and P12 read two there.

## One command

```
pip install playwright
playwright install chromium
python cup.py
```

`cup.py` fetches the three needle files at the pinned revision (and refuses any whose sha256 differs), builds the
recorded runs from `data/` and the assist-mini dataset at the leaderboard's pinned commit (and refuses any rebuilt file
whose sha256 differs; `python cup.py --dataset DIR` reads the dataset's files from DIR instead), replays every
recorded command of each of the eleven scored prompts in headless Chromium, scores what the page answered with the
leaderboard's own label for that answer, and writes the table to [RESULTS.md](RESULTS.md). The table there is written
by that command, never typed. It exits 0 only if every prompt lands within one command (four runs) of its
leaderboard count and no request left 127.0.0.1 after the files were in place; it writes the table either way.

`python cup.py --members plain-1 P10` runs a subset.

## How close the page is to the leaderboard

The page's count is exact on two prompts: Home Assistant's own (plain-1) lands 12 of 196 on the same commands as the
leaderboard run, and P10, replayed in its own recorded run, lands 16 (typed into the page, which uses the default
prompt's recorded run, it lands 12). Elsewhere it can land one command (four runs) away. The page and native needle 3
break some near ties differently (on plain-1, 23 of 196 answers differ from the leaderboard's in their exact call,
none of them a landed command; native needle itself matches 168 of 196 across the leaderboard's own runners), and
which ties come up depends on the date line and the order of the tools each leaderboard run recorded. The page's own
three runs of the unchanged prompt, whose inputs to the model (system text, tools, command text) differ only in those
bytes, landed 12, 11 and 16 of 196. RESULTS.md prints
for every prompt the page's count, the leaderboard's, the difference, and the answers no leaderboard run ever made,
which have no label and are counted unscored. Read it as within one command, not call-exact. A row offered to the
leaderboard is the harness's own count, never the page's.

## Home facts are refused

A typed prompt that names a device, area or entity of the test home would score by knowing the answers. The page runs
the same check as the harness's `prompt_carries_no_facts.py`, rule for rule (site/nofacts.js, proved against the Python
file on 994 cases by site/nofacts_check.html), and refuses such a prompt with the Python file's own reason.

## The dataset is not in this repo

[allenporter/home-assistant-datasets](https://github.com/allenporter/home-assistant-datasets) carries no licence, so
this repo commits nothing taken from it and does not redistribute it: `cup.py` fetches it from GitHub at the
leaderboard's pinned commit 45e9ac2e into `vendor/`, which is not committed, and uses it there. The recorded runs are committed as skeletons (`data/*.skel`): the files with
every string the dataset holds cut out and replaced by a numbered hole. `dataset.py fill` (run by `cup.py`) puts the
strings back from the dataset itself at commit 45e9ac2e, and writes nothing unless every result matches the sha256
in `data/pins.json`. `python dataset.py scan` exits 1 if any tracked file carries a dataset string of eight or more
characters.

## The Home Assistant component

`custom_components/hometiny_needle/` is the conversation agent the leaderboard runs used to put needle 3 in Home Assistant.
It needs `cactus-needle` 3.0.1, which Home Assistant installs from the component's manifest.
To add it, copy the `hometiny_needle` folder into your Home Assistant config's `custom_components/` folder, restart, and add it as an integration.
It passes Assist's own system prompt and tools to the model unchanged.

## Files

- `site/replay.html`, `site/engine.js`: the page and the needle calls (load once, init and complete per command).
- `site/replay_<prompt>.json` (built, not committed): per command, the exact system text, tools and command text the
  leaderboard handed needle.
- `site/labels.json` (built, not committed): the leaderboard's label for every (command, call) it scored.
- `dataset.py`, `data/`: the skeletons, their pins, the fill and the scan.
- `selftest.py`: exits 1 if the dataset fetch could fall through to the network outside `cup.py`, or a tracked file
  carries dataset text.
- `results_diff.py`: diffs a fresh RESULTS.md against the committed one, stamp and seconds left out.
- `cup.py`, `run_page.py`, `score_reading.py`: the one command, the headless runner, the scorer.
- `build_*.py`: how the site JSON was built from the leaderboard's run reports; not needed to run the cup.
