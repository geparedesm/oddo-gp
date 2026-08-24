import assert from "node:assert/strict";
import test from "node:test";

import {
  createHermesPropertyServer,
  createPropertyApiClient,
  resolveGetPropertyResult,
  REFRESH_BEFORE_ANSWERING_NOTICE,
} from "../tools/hermes-property-mcp.mjs";

const TEST_MCP_CHANNEL_TOKEN = "test-mcp-channel-token";

function createTestPropertyApiClient(options) {
  return createPropertyApiClient({
    mcpChannelToken: TEST_MCP_CHANNEL_TOKEN,
    ...options,
  });
}

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function registeredTool(server, name) {
  return server._registeredTools[name];
}

function binaryResponse(bytes, { contentType = "image/png", contentLength } = {}) {
  return new Response(bytes, {
    status: 200,
    headers: {
      "content-type": contentType,
      ...(contentLength !== undefined ? { "content-length": String(contentLength) } : {}),
    },
  });
}

test("the MCP API client requires a separate channel credential", () => {
  assert.throws(
    () => createPropertyApiClient({
      apiUrl: "https://odoo.example.test",
      token: "test-token",
    }),
    /HERMES_MCP_CHANNEL_TOKEN/,
  );
});

test("the MCP API client rejects a channel credential equal to the bearer token", () => {
  assert.throws(
    () => createPropertyApiClient({
      apiUrl: "https://odoo.example.test",
      token: "shared-test-token",
      mcpChannelToken: "shared-test-token",
    }),
    /must use different credentials/,
  );
});

test("a conversational budget and area request becomes public API filters", async () => {
  let receivedUrl;
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url, options) => {
      receivedUrl = url;
      assert.equal(options.headers.Authorization, "Bearer test-token");
      assert.equal(options.headers["X-Hermes-Channel"], "mcp");
      assert.equal(options.headers["X-Hermes-MCP-Token"], TEST_MCP_CHANNEL_TOKEN);
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

test("a conversational zone request becomes a public API zone filter", async () => {
  let receivedUrl;
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url) => {
      receivedUrl = url;
      return jsonResponse(200, { properties: [] });
    },
  });

  await client.searchProperties({ zone: "Near the central plaza", maxRent: 1200 });

  assert.equal(receivedUrl.searchParams.get("zone"), "Near the central plaza");
  assert.equal(receivedUrl.searchParams.get("max_rent"), "1200");
});

test("an empty conversational search returns an empty public result", async () => {
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async () => jsonResponse(200, { properties: [] }),
  });

  assert.deepEqual(await client.searchProperties({ maxRent: 500 }), { properties: [] });
});

test("an invalid conversational request surfaces the public API validation error", async () => {
  const client = createTestPropertyApiClient({
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
  const client = createTestPropertyApiClient({
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

test("a consented enquiry is posted to the encoded public unit URL", async () => {
  let receivedUrl;
  let receivedOptions;
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test", token: "test-token",
    fetchImpl: async (url, options) => {
      receivedUrl = url;
      receivedOptions = options;
      return jsonResponse(201, { message: "Your enquiry was received for manager review." });
    },
  });
  const enquiry = { name: "Ana", phone: "+1555", consent: true, visit_requested: true, channel: "Instagram Campaign Q3", budget: 1200 };
  assert.deepEqual(await client.submitEnquiry("CP 001", enquiry), { message: "Your enquiry was received for manager review." });
  assert.equal(receivedUrl.pathname, "/api/hermes/properties/CP%20001/enquiries");
  assert.equal(receivedOptions.method, "POST");
  assert.equal(receivedOptions.headers["Content-Type"], "application/json");
  assert.equal(receivedOptions.headers["X-Hermes-Channel"], "mcp");
  assert.equal(receivedOptions.headers["X-Hermes-MCP-Token"], TEST_MCP_CHANNEL_TOKEN);
  assert.deepEqual(JSON.parse(receivedOptions.body), enquiry);
  assert.equal(JSON.parse(receivedOptions.body).budget, 1200);
});

function sessionOriginExtra({ platform = "whatsapp", chatType = "dm", userId } = {}) {
  return {
    _meta: {
      "com.nousresearch.hermes/session": {
        platform,
        chat_type: chatType,
        user_id: userId,
      },
    },
  };
}

test("only the enquiry tool opts in to private session-origin metadata", () => {
  const server = createHermesPropertyServer(() => ({}));
  const enquiryTool = registeredTool(server, "submit_property_enquiry");

  assert.equal(enquiryTool._meta["com.nousresearch.hermes/session-origin"], true);
  assert.equal(enquiryTool.inputSchema.shape.phone.isOptional(), true);
  assert.equal(enquiryTool.inputSchema.shape.whatsapp_sender, undefined);
  assert.equal(registeredTool(server, "search_properties")._meta, undefined);
});

test("WhatsApp Cloud metadata supplies a normalized sender without model-visible phone", async () => {
  let receivedBody;
  const server = createHermesPropertyServer(() => ({
    submitEnquiry(_propertyCode, enquiry) {
      receivedBody = enquiry;
      return { message: "accepted" };
    },
  }));

  await registeredTool(server, "submit_property_enquiry").handler(
    { property_code: "CP-001", name: "Ana", consent: true },
    sessionOriginExtra({ platform: "whatsapp_cloud", userId: "593999000111" }),
  );

  assert.equal(receivedBody.whatsapp_sender, "593999000111");
  assert.equal(Object.hasOwn(receivedBody, "phone"), false);
});

test("Baileys metadata supplies a normalized sender from a device JID", async () => {
  let receivedBody;
  const server = createHermesPropertyServer(() => ({
    submitEnquiry(_propertyCode, enquiry) {
      receivedBody = enquiry;
      return { message: "accepted" };
    },
  }));

  await registeredTool(server, "submit_property_enquiry").handler(
    { property_code: "CP-001", name: "Ana", consent: true },
    sessionOriginExtra({ userId: "593999000222:17@s.whatsapp.net" }),
  );

  assert.equal(receivedBody.whatsapp_sender, "593999000222");
});

test("trusted WhatsApp metadata overrides spoofed sender and phone arguments", async () => {
  let receivedBody;
  const server = createHermesPropertyServer(() => ({
    submitEnquiry(_propertyCode, enquiry) {
      receivedBody = enquiry;
      return { message: "accepted" };
    },
  }));

  await registeredTool(server, "submit_property_enquiry").handler(
    {
      property_code: "CP-001",
      name: "Ana",
      phone: "+12025550199",
      whatsapp_sender: "+12025550188",
      consent: true,
    },
    sessionOriginExtra({ userId: "593999000333@s.whatsapp.net" }),
  );

  assert.equal(receivedBody.whatsapp_sender, "593999000333");
  assert.equal(Object.hasOwn(receivedBody, "phone"), false);
});

test("invalid authenticated WhatsApp identity cannot fall back to a model phone", async () => {
  const server = createHermesPropertyServer(() => ({
    submitEnquiry() {
      assert.fail("invalid authenticated identity must not reach Odoo");
    },
  }));

  await assert.rejects(
    registeredTool(server, "submit_property_enquiry").handler(
      {
        property_code: "CP-001",
        name: "Ana",
        phone: "+12025550199",
        consent: true,
      },
      sessionOriginExtra({ userId: "not-a-whatsapp-identity" }),
    ),
    /authenticated WhatsApp sender metadata is invalid/i,
  );
});

test("non-WhatsApp and non-DM sessions cannot spoof an automatic sender", async () => {
  for (const extra of [
    sessionOriginExtra({ platform: "web", userId: "593999000444" }),
    sessionOriginExtra({ platform: "email", userId: "593999000444" }),
    sessionOriginExtra({ platform: "local", userId: "593999000444" }),
    sessionOriginExtra({ chatType: "group", userId: "593999000444" }),
  ]) {
    const server = createHermesPropertyServer(() => ({
      submitEnquiry() {
        assert.fail("an untrusted sender must not reach Odoo");
      },
    }));
    await assert.rejects(
      registeredTool(server, "submit_property_enquiry").handler(
        {
          property_code: "CP-001",
          name: "Ana",
          whatsapp_sender: "593999000444",
          consent: true,
        },
        extra,
      ),
      /explicit phone/i,
    );
  }
});

test("an explicit phone remains the fallback without trusted WhatsApp metadata", async () => {
  let receivedBody;
  const server = createHermesPropertyServer(() => ({
    submitEnquiry(_propertyCode, enquiry) {
      receivedBody = enquiry;
      return { message: "accepted" };
    },
  }));

  await registeredTool(server, "submit_property_enquiry").handler({
    property_code: "CP-001",
    name: "Ana",
    phone: "+12025550199",
    consent: true,
  });

  assert.equal(receivedBody.phone, "+12025550199");
  assert.equal(Object.hasOwn(receivedBody, "whatsapp_sender"), false);
});

test("a property photo is fetched from the encoded authenticated binary route", async () => {
  let receivedUrl;
  let receivedOptions;
  const bytes = new Uint8Array([1, 2, 3, 4]);
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url, options) => {
      receivedUrl = url;
      receivedOptions = options;
      return binaryResponse(bytes);
    },
  });

  const photo = await client.getPropertyPhoto("CP 001");

  assert.equal(receivedUrl.pathname, "/api/hermes/properties/CP%20001/photo");
  assert.equal(receivedOptions.method, "GET");
  assert.equal(receivedOptions.headers.Authorization, "Bearer test-token");
  assert.equal(receivedOptions.headers["X-Hermes-Channel"], "mcp");
  assert.equal(photo.mimeType, "image/png");
  assert.equal(photo.data, Buffer.from(bytes).toString("base64"));
});

test("an unauthorized photo request surfaces the public API error", async () => {
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async () => jsonResponse(401, { error: { code: "unauthorized", message: "A valid bearer token is required." } }),
  });

  await assert.rejects(
    client.getPropertyPhoto("CP-001"),
    /Property API request failed \(401\): A valid bearer token is required\./,
  );
});

test("a photo response with a disallowed MIME type is rejected", async () => {
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async () => binaryResponse(new Uint8Array([1, 2, 3]), { contentType: "application/pdf" }),
  });

  await assert.rejects(client.getPropertyPhoto("CP-001"), /unsupported content type/);
});

test("a photo response over the size limit is rejected using the Content-Length header", async () => {
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async () => binaryResponse(new Uint8Array([1, 2, 3]), { contentLength: 11 * 1024 * 1024 }),
  });

  await assert.rejects(client.getPropertyPhoto("CP-001"), /exceeds the \d+-byte limit/);
});

test("a photo response over the size limit is rejected using the actual byte count", async () => {
  const oversizedBytes = new Uint8Array(10 * 1024 * 1024 + 1);
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async () => binaryResponse(oversizedBytes),
  });

  await assert.rejects(client.getPropertyPhoto("CP-001"), /exceeds the \d+-byte limit/);
});

test("get_property returns an ImageContent block alongside the JSON text when a photo is available", async () => {
  const bytes = new Uint8Array([9, 9, 9]);
  const property = { code: "CP-001", photo_url: "/api/hermes/properties/CP-001/photo" };
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url) => {
      if (url.pathname.endsWith("/photo")) {
        return binaryResponse(bytes);
      }
      return jsonResponse(200, { property });
    },
  });

  const result = await resolveGetPropertyResult(client, "CP-001");

  assert.equal(result.content.length, 2);
  assert.deepEqual(result.content[0], { type: "text", text: JSON.stringify({ property }) });
  assert.deepEqual(result.content[1], { type: "image", data: Buffer.from(bytes).toString("base64"), mimeType: "image/png" });
  assert.deepEqual(result.structuredContent, { property });
});

test("get_property omits the ImageContent block and does not fetch a photo when photo_url is null", async () => {
  const property = { code: "CP-002", photo_url: null };
  let photoRequested = false;
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url) => {
      if (url.pathname.endsWith("/photo")) {
        photoRequested = true;
      }
      return jsonResponse(200, { property });
    },
  });

  const result = await resolveGetPropertyResult(client, "CP-002");

  assert.equal(photoRequested, false);
  assert.deepEqual(result.content, [{ type: "text", text: JSON.stringify({ property }) }]);
  assert.deepEqual(result.structuredContent, { property });
});

test("search_properties and get_property descriptions require refreshing current data before answering", () => {
  const server = createHermesPropertyServer(() =>
    createTestPropertyApiClient({ apiUrl: "https://odoo.example.test", token: "test-token" }),
  );

  assert.match(REFRESH_BEFORE_ANSWERING_NOTICE, /never infer/i);
  assert.match(REFRESH_BEFORE_ANSWERING_NOTICE, /current data/i);
  assert.ok(registeredTool(server, "search_properties").description.includes(REFRESH_BEFORE_ANSWERING_NOTICE));
  assert.ok(registeredTool(server, "get_property").description.includes(REFRESH_BEFORE_ANSWERING_NOTICE));
});

test("get_property_photo is described as a mandatory re-check before answering photo questions", () => {
  const server = createHermesPropertyServer(() =>
    createTestPropertyApiClient({ apiUrl: "https://odoo.example.test", token: "test-token" }),
  );

  const description = registeredTool(server, "get_property_photo").description;

  assert.match(description, /MUST call/);
  assert.match(description, /photo/i);
  assert.match(description, /re-queries the current property record/i);
  assert.match(description, /never answer a photo question from conversation history/i);
});

test("get_property_photo re-fetches the current record and attaches the image when a photo now exists", async () => {
  const bytes = new Uint8Array([7, 7, 7]);
  const property = { code: "CU2026-0003", photo_url: "/api/hermes/properties/CU2026-0003/photo" };
  let getPropertyCalls = 0;
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url) => {
      if (url.pathname.endsWith("/photo")) {
        return binaryResponse(bytes);
      }
      getPropertyCalls += 1;
      return jsonResponse(200, { property });
    },
  });
  const server = createHermesPropertyServer(() => client);

  const result = await registeredTool(server, "get_property_photo").handler({ property_code: "CU2026-0003" });

  assert.equal(getPropertyCalls, 1);
  assert.equal(result.content.length, 2);
  assert.deepEqual(result.content[0], { type: "text", text: JSON.stringify({ property }) });
  assert.deepEqual(result.content[1], { type: "image", data: Buffer.from(bytes).toString("base64"), mimeType: "image/png" });
  assert.deepEqual(result.structuredContent, { property });
});

test("get_property_photo does not invent a photo when the current record has none", async () => {
  const property = { code: "CU2026-0003", photo_url: null };
  let photoRequested = false;
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url) => {
      if (url.pathname.endsWith("/photo")) {
        photoRequested = true;
      }
      return jsonResponse(200, { property });
    },
  });
  const server = createHermesPropertyServer(() => client);

  const result = await registeredTool(server, "get_property_photo").handler({ property_code: "CU2026-0003" });

  assert.equal(photoRequested, false);
  assert.deepEqual(result.content, [{ type: "text", text: JSON.stringify({ property }) }]);
  assert.deepEqual(result.structuredContent, { property });
});

test("a zone-only conversational search omits budget and size filters", async () => {
  let receivedUrl;
  const client = createTestPropertyApiClient({
    apiUrl: "https://odoo.example.test",
    token: "test-token",
    fetchImpl: async (url) => {
      receivedUrl = url;
      return jsonResponse(200, { properties: [] });
    },
  });

  await client.searchProperties({ zone: "Jocay", limit: 20 });

  assert.equal(receivedUrl.searchParams.get("zone"), "Jocay");
  assert.equal(receivedUrl.searchParams.get("availability"), "available");
  assert.equal(receivedUrl.searchParams.get("limit"), "20");
  assert.equal(receivedUrl.searchParams.has("max_rent"), false);
  assert.equal(receivedUrl.searchParams.has("min_area"), false);
});

test("search_properties, get_available_properties and submit_property_enquiry never ask for budget or size upfront", () => {
  const server = createHermesPropertyServer(() =>
    createTestPropertyApiClient({ apiUrl: "https://odoo.example.test", token: "test-token" }),
  );

  const searchDescription = registeredTool(server, "search_properties").description;
  const availableDescription = registeredTool(server, "get_available_properties").description;
  const enquiryDescription = registeredTool(server, "submit_property_enquiry").description;

  for (const description of [searchDescription, availableDescription, enquiryDescription]) {
    assert.match(description, /never ask|volunteered/i);
    assert.doesNotMatch(description, /always ask.*budget/i);
  }
});
