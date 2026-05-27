# Wikipedia Search Cell

A frontend-only cell type that searches Wikipedia articles via the public MediaWiki Action API and renders results as clickable links.

## Overview

This cell allows users to search Wikipedia directly from the workspace, browse article titles and excerpts, and open articles in a new tab. It uses the Wikipedia Action API with CORS (`origin=*`), requiring no backend or API keys.

## Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `query` | string | — | Search term (required) |
| `language` | string | `en` | Wikipedia language code |
| `limit` | number | `10` | Max results (1–50) |

## Usage

1. Type a search term (e.g. "Artificial Intelligence")
2. Select the Wikipedia language (e.g. EN, PT, ES)
3. Click "Search" or press Enter
4. Browse results with titles, excerpts, and direct links

## Technical Notes

- **Frontend-only**: No backend required. Calls Wikipedia API directly from the browser.
- **API**: `https://{language}.wikipedia.org/w/api.php?action=query&list=search`
- **CORS**: Uses `origin=*` parameter for cross-origin support
- **Rate limits**: Subject to Wikipedia's rate limiting policies
