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
| `title` | Has description | Required |
| `author` | Has publication author (subobject) | Parsed into first/middle/last name |
| `year` | Has publication year | |
| `journal` | Has journal | |
| `booktitle` | Has journal | For conference proceedings |
| `doi` | Has DOI | |
| `pmid` | Has PubMed ID | |
| `volume` | Has volume | |
| `number` | Has issue | |
| `pages` | Has pages | `--` converted to en-dash |
| `abstract` | Has abstract | |
| `keywords` | Has keyword | Comma-separated |
| `url` | Has website | |
| `project` | Has project | Wiki page name |
| `component` | Has component | Wiki page name, comma-separated for multiple |
| `equipment` | Has equipment used | Wiki page name, comma-separated for multiple |
| `technique` | Has technique | Wiki page name, comma-separated for multiple |
| `attachment` | Has attachment | File link |
| `publication_status` | Has publication status | Overrides auto-detected status |

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
- Skips pages where content hasn't changed
- Reports a summary of created/updated/unchanged/error counts

## GitHub Action

The workflow at `.github/workflows/sync-to-wiki.yml` runs automatically on pushes to main that modify `.bib` files, `scripts/`, or `config.json`. It can also be triggered manually from the Actions tab.

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
4. Grant permissions: **Edit existing pages**, **Create, edit, and move pages**, **High-volume editing**
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

Generated pages use the Publication category schema from [labki-ontology](https://github.com/labki-org/labki-ontology), which provides:

- **Publication** category with bibliographic metadata properties
- **Has publication author** subobject with first/middle/last name fields and optional Person page links
- Integration with Equipment, Component, and Technique categories for cross-referencing

The wiki must have the ontology installed via [OntologySync](https://github.com/labki-org/OntologySync) and templates generated by [SemanticSchemas](https://github.com/labki-org/SemanticSchemas) for pages to render correctly.

## Contributing

To add a Miniscope-related publication:

1. Fork this repository
2. Add your BibTeX entry to `references.bib`
3. Open a pull request

Please ensure your entry includes at minimum: `title`, `author`, `year`, and `doi` (if available).
