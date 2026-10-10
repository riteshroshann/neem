# 6. Astro with React islands for the web

Date: 2026-10-10
Status: accepted

## Context

The site is mostly editorial: an index of the hottest schoolyards, a long-form page per school, a method page. Two parts are heavy and interactive: the drag-a-tree map and the child twin chart.

## Decision

Astro for pages (static HTML, near-zero JS by default), React islands for the interactive pieces, TypeScript strict, Bun and Biome. The API client is generated from the OpenAPI schema.

## Consequences

- Editorial pages load instantly and are crawlable.
- The interactive island owns its state; pages pass it only a school id and pre-fetched data.
- This departs from the default Vite + React SPA because most of the site is content, not app.
