import assert from "node:assert/strict";
import test from "node:test";

import { createPropertyApiClient } from "../tools/hermes-property-mcp.mjs";

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("a conversational budget and area request becomes public API filters", async () => {
  let receivedUrl;
  const client = createPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url, options) => {
      receivedUrl = url;
      assert.equal(options.headers.Authorization, "Bearer test-token");
      return jsonResponse(200, { properties: [{ code: "CP-001", name: "Central Tower" }] });
    },
  });

  const result = await client.searchProperties({ minArea: 100, maxRent: 1200, limit: 5 });

  assert.deepEqual(result, { properties: [{ code: "CP-001", name: "Central Tower" }] });
  assert.equal(receivedUrl.pathname, "/api/hermes/properties");
  assert.equal(receivedUrl.searchParams.get("availability"), "available");
  assert.equal(receivedUrl.searchParams.get("min_area"), "100");
  assert.equal(receivedUrl.searchParams.get("max_rent"), "1200");
  assert.equal(receivedUrl.searchParams.get("limit"), "5");
});

test("an empty conversational search returns an empty public result", async () => {
  const client = createPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async () => jsonResponse(200, { properties: [] }),
  });

  assert.deepEqual(await client.searchProperties({ maxRent: 500 }), { properties: [] });
});

test("an invalid conversational request surfaces the public API validation error", async () => {
  const client = createPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async () => jsonResponse(400, {
      error: { code: "invalid_parameter", message: "Use valid non-negative filters and a limit from 1 to 50." },
    }),
  });

  await assert.rejects(
    client.searchProperties({ maxRent: -1 }),
    /Property API request failed \(400\): Use valid non-negative filters and a limit from 1 to 50\./,
  );
});

test("a property code is encoded before requesting public details", async () => {
  let receivedUrl;
  const client = createPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url) => {
      receivedUrl = url;
      return jsonResponse(200, { property: { code: "CP 001" } });
    },
  });

  await client.getProperty("CP 001");

  assert.equal(receivedUrl.pathname, "/api/hermes/properties/CP%20001");
});
