# Miniscope Citations

A community-maintained bibliography of publications related to the UCLA Miniscope Project. Citations stored as BibTeX are automatically converted and synced to the [Miniscope wiki](https://miniscope.org) as structured Publication pages.

## How it works

```
references.bib          (you edit this)
       ↓
bib_to_wikitext.py      (converts to MediaWiki wikitext)
       ↓
output/*.wikitext        (one page per citation)
       ↓
push_to_wiki.py          (pushes to wiki via MediaWiki API)
```

A GitHub Action runs this pipeline automatically whenever `.bib` files are updated on main.

## Adding a citation

1. Edit `references.bib` (or create additional `.bib` files and register them in `config.json`)
2. Add a standard BibTeX entry:

```bibtex
@article{smith2024,
  title     = {Title of the paper},
  author    = {Smith, Jane A. and Doe, John and Lee, Sarah K.},
  journal   = {Journal Name},
  volume    = {12},
  number    = {3},
  pages     = {100--115},
  year      = {2024},
  doi       = {10.1234/example.2024.56789},
  abstract  = {Brief description of the paper...},
  keywords  = {keyword1, keyword2, keyword3},
  component = {UCLA Miniscope v4},
  technique = {Calcium Imaging}
}
```

3. Commit and push (or open a pull request)

The GitHub Action will convert the entry and push it to the wiki as a Publication page.

### BibTeX entry key

The entry key becomes the wiki page name — e.g., `Publication/smith_2024_novel`. Keys are automatically normalized by CI to the format `{author}_{year}_{first_title_word}`, so you don't need to worry about getting the key right.

### Supported BibTeX fields

| BibTeX field | Wiki property | Notes |
|---|---|---|
| `title` | Has title | Required. The full paper title (no longer mapped to Has description) |
| `author` | Publication author (subobject) | Parsed into first/middle/last name; first author flagged |
| `year` | Has publication year | Integer; used for chronological sorting in the curated library |
| `journal` | Has journal | |
| `booktitle` | Has journal | For conference proceedings |
| `doi` | Has DOI | |
| `pmid` | Has PubMed ID | |
| `volume` | Has volume | |
| `number` | Has issue | |
| `pages` | Has pages | `--` converted to en-dash |
| `abstract` | Has abstract | Full paper abstract |
| `keywords` | Has keyword | Tags drawn from `vocabulary.yaml/keywords`. Comma-separated for multiple. |
| `url` | Has website | |
| `project` | Has project | Wiki page name. Drawn from `vocabulary.yaml/projects` (the umbrella tool family — e.g. UCLA Miniscope v4). |
| `paper_type` | Has paper type | The *intent* of the paper (Science / Methods / Software / Tool Paper / Review / Opinion / Protocol) from `vocabulary.yaml/paper_types`. Distinct from `Has publication type` which captures *format* (auto-derived from `@type`). |
| `attachment` | Has attachment | File link |
| `publication_status` | Has publication status | Overrides auto-detected status |

The pipeline emits each author as a `{{Publication author/subobject|...}}` template call with `has_first_name` / `has_middle_name` / `has_last_name` / `has_is_first_author` fields. To link an author entry to a wiki Person page or attach an ORCID, edit the wiki page directly *outside* the citations-sync markers — the sync preserves manual edits there.

### Supported entry types

| BibTeX type | Publication type |
|---|---|
| `article` | Journal Article |
| `inproceedings`, `conference` | Conference Paper |
| `incollection` | Book Chapter |
| `phdthesis`, `mastersthesis` | Thesis |
| `book` | Book Chapter |
| `unpublished` | Preprint |
| `misc` (with `eprint`) | Preprint |

### Author name formats

Both standard BibTeX formats are supported:

- `Last, First Middle` — e.g., `Smith, Jane A.`
- `First Middle Last` — e.g., `Jane A. Smith`

The first author listed automatically gets the "first author" flag.

## Removing a citation

Delete the BibTeX entry from `references.bib` and open a pull request. The PR summary will list removed entries and note that their wiki pages will be deleted on merge.

When the PR merges, the sync job automatically deletes the corresponding wiki pages via the MediaWiki API. The bot account must have the **Delete pages** permission (see [Creating a bot account](#creating-a-bot-account)).

## Manual enrichment on the wiki

The converter wraps generated content in markers:

```
<!-- citations-sync start -->
(auto-generated content)
<!-- citations-sync end -->
[[Category:Publication]]
```

Content added **outside the markers** on the wiki is preserved across syncs. This is where you can manually add links to Miniscope components, equipment, or techniques:

```
<!-- citations-sync end -->
[[Category:Publication]]

== Related tools ==
* [[Component:UCLA Miniscope v4]]
* [[Equipment:Miniscope DAQ]]
```

## Running locally

### Prerequisites

- Python 3.10+

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Convert BibTeX to wikitext

```bash
python scripts/bib_to_wikitext.py
```

Output is written to `output/`. Each entry produces a `.wikitext` file and the full set is indexed in `output/manifest.json`.

### Push to wiki

Requires a MediaWiki bot account. Set environment variables and run:

```bash
export WIKI_API_URL="https://miniscope.org/api.php"
export WIKI_BOT_USERNAME="CitationsBot@citations-sync"
export WIKI_BOT_PASSWORD="your-bot-password"

python scripts/push_to_wiki.py
```

The push script:
- Creates new pages for new entries
- Updates existing pages by replacing content between markers only
- Deletes pages for entries removed from the `.bib` files
- Skips pages where content hasn't changed
- Reports a summary of created/updated/unchanged/deleted/error counts

## GitHub Action

The workflow at `.github/workflows/sync-to-wiki.yml` runs automatically on pushes to main that modify `.bib` files, `scripts/`, or `config.json`. It can also be triggered manually from the Actions tab.

### Re-syncing older changes

The sync job normally compares against the previous commit (`HEAD~1`). If a sync fails (e.g., the bot lacked permissions) and the changes are already merged, you can re-run it against an older commit:

1. Go to **Actions → Sync citations to wiki → Run workflow**
2. Enter a commit SHA in the **base_ref** field (e.g., the commit before the failed change)
3. Click **Run workflow**

This will diff the current state against that older commit and re-apply any creates, updates, or deletions that were missed.

### Required secrets

Set these in the repository settings under Settings > Secrets and variables > Actions:

| Secret | Description | Example |
|---|---|---|
| `WIKI_API_URL` | MediaWiki API endpoint | `https://miniscope.org/api.php` |
| `WIKI_BOT_USERNAME` | Bot account username | `CitationsBot@citations-sync` |
| `WIKI_BOT_PASSWORD` | Bot account password | (from Special:BotPasswords) |

### Creating a bot account

1. Log in to the wiki as an admin
2. Go to `Special:BotPasswords`
3. Create a new bot with the name `citations-sync`
4. Grant permissions: **Edit existing pages**, **Create, edit, and move pages**, **Delete pages**, **High-volume editing**
5. Save the generated password — this is `WIKI_BOT_PASSWORD`
6. The username is `YourUsername@citations-sync` — this is `WIKI_BOT_USERNAME`

## Configuration

`config.json` controls the converter:

```json
{
  "wiki_api_url": "https://miniscope.org/api.php",
  "page_prefix": "Publication/",
  "bib_files": ["references.bib"]
}
```

| Field | Description |
|---|---|
| `wiki_api_url` | Wiki API URL (used for documentation; the Action uses the secret) |
| `page_prefix` | Page name prefix within the namespace |
| `page_namespace` | Optional. MediaWiki namespace for generated pages (default: main namespace) |
| `bib_files` | List of `.bib` files to process (relative to repo root) |

You can organize citations into multiple `.bib` files (e.g., `miniscope-v4.bib`, `calcium-imaging.bib`) and list them all in `bib_files`.

## Ontology compatibility

Generated pages use the self-sufficient **Category:Publication** schema (no Document parent) shipped by [SchemaSync](https://github.com/labki-org/SchemaSync), which provides:

- **Publication** category with bibliographic metadata properties (title, abstract, journal/volume/issue/pages, DOI, PMID, publication year/type/status)
- **Publication author** subobject with first/middle/last name fields plus `Is first author`, optional `Has person` link to a wiki Person page, and optional ORCID
- **Template:Category/Publication** masthead — renders title, byline (from Publication-author subobjects), citation line, identifiers, abstract, and keyword/topic chips
- **Template:UI/publications_library** — drop into a content page (e.g. `Publications`) to get a curated library view with stat strip, faceted browse by type/topic/year, and a recent-publications feed
- Integration with Equipment, Component, Technique, and Project categories for cross-referencing (set manually on the wiki page after sync; the citations-sync markers preserve those edits)

The wiki must have the schema installed via [SchemaSync](https://github.com/labki-org/SchemaSync) and templates generated by [SemanticSchemas](https://github.com/labki-org/SemanticSchemas) for pages to render correctly.

## Contributing

To add a Miniscope-related publication:

1. Fork this repository
2. Add your BibTeX entry to `references.bib`
3. Open a pull request

Please ensure your entry includes at minimum: `title`, `author`, `year`, and `doi` (if available).
