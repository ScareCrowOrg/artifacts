# Wikipedia Search Cell — Documentation

## Architecture

This cell follows **Pattern A (frontend-only)** from the cell architecture:

- **WikipediaSearchCell.ts**: Implements `BaseCell`. Calls the public Wikipedia MediaWiki Action API directly from the browser using `fetch` with `origin=*` for CORS.
- **View.vue**: Vue 3 component with search input, language selector, results list, and state handling (idle, searching, results, no results, error).
- **Translations**: i18n support for English and Portuguese (Brazil).

## API Reference

This cell uses the [Wikipedia Action API](https://www.mediawiki.org/wiki/API:Search):

```
https://{language}.wikipedia.org/w/api.php
  ?action=query
  &list=search
  &srsearch={query}
  &srlimit={limit}
  &format=json
  &origin=*
```

### Response Format

```json
{
  "query": {
    "searchinfo": { "totalhits": 1234 },
    "search": [
      {
        "pageid": 123,
        "title": "Article Title",
        "snippet": "Article excerpt with <span class=\"searchmatch\">highlighted</span> terms"
      }
    ]
  }
}
```

## States

| State | Behavior |
|-------|----------|
| **Idle** | Empty state with placeholder text |
| **Searching** | Animated spinner, disabled inputs |
| **Results** | List of result cards with title, snippet, and link |
| **No results** | "No results" message with suggestion to try again |
| **Error** | Error banner with message (network, API, parsing) |

## Rate Limiting

Wikipedia applies rate limits to API requests. If you receive HTTP 429 responses, reduce request frequency. The cell has no built-in throttling — users should respect Wikipedia's usage policies.

## See Also

- [Wikipedia Action API Documentation](https://www.mediawiki.org/wiki/API:Search)
- [Wikipedia API Sandbox](https://en.wikipedia.org/wiki/Special:ApiSandbox)
