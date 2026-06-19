# status.yonerai.com design

## Goal

OpenAI/Claude-style status page with broad YonerAI categories. A category click expands into the detailed status items for that field.

## Categories

- Public surfaces
  - Website
  - Web demo
- Core APIs
  - API
  - Run API
  - Provider integrations
- Identity and access
  - Auth
- Developer and release
  - Docs
  - GitHub repository
  - Local runtime docs
- Infrastructure
  - AWS staging

## Truth model

- All categories are gray.
- All child components are gray.
- Status text is `Preparing`.
- Uptime is `no data`.
- Monitoring is `not connected`.
- No production operation claim is made.
- No incidents are invented.

## Interaction model

- Hover over any 90-day bar: show tooltip with date and `No data exists for this day.`
- Click a category: expand or collapse its child component status rows.
- Click a child component: expand factual details for that component.
- Subscribe and history buttons show preparation alerts only.

## Language model

- Default language is detected client-side.
- Japanese is used when `navigator.languages` starts with `ja` or the browser timezone is `Asia/Tokyo`.
- English is used for EU/global/overseas visitors.
- Manual overrides:
  - `?lang=ja` or `?lang=jp`
  - `?lang=en`, `?lang=eu`, or `?lang=global`
- Open Graph preview text remains English by default because crawlers usually do not execute client-side JavaScript.
