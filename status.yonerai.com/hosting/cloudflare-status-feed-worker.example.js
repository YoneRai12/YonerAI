/*
 * Example Cloudflare Worker for same-origin YonerAI Status feeds.
 *
 * This is a deployment pattern, not a production configuration. Do not put
 * secrets, private runtime inventory, break-glass details, raw logs, or user
 * data in the public feed.
 *
 * Routes:
 * - GET /status-feed.json   -> current yonerai.status.feed.v1 payload
 * - GET /status-feed/events -> Server-Sent Events stream for live updates
 */

const headers = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

const eventHeaders = {
  "content-type": "text/event-stream; charset=utf-8",
  "cache-control": "no-store",
  "connection": "keep-alive",
  "x-content-type-options": "nosniff",
};

function localized(ja, en) {
  return { ja, en };
}

function currentFeed() {
  /*
   * Replace this with the result of the public-safe pipeline:
   *
   * internal monitor output
   * -> yonerai.status.monitor.v1
   * -> tools/build-status-pipeline.mjs
   * -> tools/validate-status-feed.mjs
   * -> same-origin feed endpoint
   */
  return {
    schema_version: "yonerai.status.feed.v1",
    generated_at: new Date().toISOString(),
    locale_default: "ja",
    range: {
      days: 1,
      start: "2026-06-01",
      end: "2026-06-01",
    },
    contract_note: localized(
      "これは Cloudflare endpoint 接続例です。本番監視データではありません。",
      "This is a Cloudflare endpoint integration example. It is not production monitoring data.",
    ),
    states: {
      not_started: {
        color: "#aeb6c2",
        label: localized("準備中", "Not started"),
      },
    },
    categories: [
      {
        id: "public-surfaces",
        name: localized("公開サーフェス", "Public surfaces"),
        children: [
          {
            id: "website",
            name: localized("Website", "Website"),
            fact: localized(
              "この endpoint 例では live monitoring を claim しません。",
              "This endpoint example does not claim live monitoring.",
            ),
            monitoring: localized("未接続", "Not connected"),
            claim: localized("本番運用は未主張", "No production operation claim"),
            state: "not_started",
            days: [
              {
                index: 0,
                date: "2026-06-01",
                date_label: localized("2026年6月1日", "2026-06-01"),
                state: "not_started",
                label: localized("準備中", "Not started"),
                message: localized(
                  "監視データはまだ接続していません。",
                  "Monitoring data is not connected yet.",
                ),
                source: "cloudflare-worker-example",
              },
            ],
          },
        ],
      },
    ],
    incidents: [],
  };
}

function jsonResponse(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers });
}

function notFound() {
  return jsonResponse({ error: "not_found" }, 404);
}

function sseResponse(request) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      function send(event, data) {
        controller.enqueue(encoder.encode(`event: ${event}\n`));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      }

      send("status-feed", currentFeed());

      const timer = setInterval(() => {
        send("ping", { at: new Date().toISOString() });
      }, 25000);

      request.signal.addEventListener("abort", () => {
        clearInterval(timer);
        controller.close();
      });
    },
  });

  return new Response(stream, { headers: eventHeaders });
}

export default {
  fetch(request) {
    const url = new URL(request.url);
    if (request.method !== "GET") {
      return jsonResponse({ error: "method_not_allowed" }, 405);
    }
    if (url.pathname === "/status-feed.json") {
      return jsonResponse(currentFeed());
    }
    if (url.pathname === "/status-feed/events") {
      return sseResponse(request);
    }
    return notFound();
  },
};
