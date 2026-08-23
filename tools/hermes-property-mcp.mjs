import path from "node:path";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const DEFAULT_API_URL = "http://127.0.0.1:8069";
const MAX_LIMIT = 50;
const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
const ALLOWED_PHOTO_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);
// zod's built-in .email() emits a JSON Schema pattern with negative lookaheads
// (?!...), which Groq's tool-schema compiler rejects as "not a valid regex".
// This lookahead-free pattern keeps basic shape validation working everywhere.
const SIMPLE_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function optionalNonNegativeNumber(description) {
  return z.number().finite().nonnegative().optional().describe(description);
}

function optionalLimit() {
  return z.number().int().min(1).max(MAX_LIMIT).optional().describe("Maximum number of properties to return (1-50). Defaults to 20.");
}

function optionalZone() {
  return z.string().trim().min(1).max(128).optional().describe("The prospect's desired zone/location (street, neighborhood or landmark). Always ask for this before searching.");
}

// A unit's availability, price, or photo can change between messages (e.g. a
// manager updates the photo mid-conversation). Tool descriptions must repeat
// this so the model never answers from a stale earlier reply in history.
export const REFRESH_BEFORE_ANSWERING_NOTICE =
  "Always call this tool to fetch current data before answering any question about availability, unit details, or photos — even if the conversation history already contains an earlier answer about this unit. Never infer photo availability, price or availability status from history; any of these can change at any time, so a fresh call is required every time the prospect asks again.";

function requireConfiguration(value, name) {
  if (!value) {
    throw new Error(`${name} must be configured before using the Hermes property tools.`);
  }
  return value;
}

export function createPropertyApiClient({
  apiUrl = process.env.HERMES_PROPERTY_API_URL || DEFAULT_API_URL,
  token = process.env.HERMES_API_TOKEN,
  fetchImpl = globalThis.fetch,
} = {}) {
  const baseUrl = new URL(apiUrl);
  const authorizationToken = requireConfiguration(token, "HERMES_API_TOKEN");

  async function request(pathname, parameters = {}, requestOptions = {}) {
    const url = new URL(pathname, baseUrl);
    for (const [name, value] of Object.entries(parameters)) {
      if (value !== undefined) {
        url.searchParams.set(name, String(value));
      }
    }

    const response = await fetchImpl(url, {
      method: requestOptions.method || "GET",
      headers: { Authorization: `Bearer ${authorizationToken}`, "X-Hermes-Channel": "mcp", ...(requestOptions.body ? { "Content-Type": "application/json", "Idempotency-Key": requestOptions.idempotencyKey || randomUUID() } : {}) },
      body: requestOptions.body ? JSON.stringify(requestOptions.body) : undefined,
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const message = payload?.error?.message || "The public property API request failed.";
      throw new Error(`Property API request failed (${response.status}): ${message}`);
    }
    return payload;
  }

  async function requestPhoto(pathname) {
    const url = new URL(pathname, baseUrl);
    const response = await fetchImpl(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${authorizationToken}`, "X-Hermes-Channel": "mcp" },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      const message = payload?.error?.message || "The public property photo request failed.";
      throw new Error(`Property API request failed (${response.status}): ${message}`);
    }
    const mimeType = (response.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    if (!ALLOWED_PHOTO_MIME_TYPES.has(mimeType)) {
      throw new Error(`Property photo rejected: unsupported content type "${mimeType || "unknown"}".`);
    }
    const contentLength = response.headers.get("content-length");
    if (contentLength !== null && Number(contentLength) > MAX_PHOTO_BYTES) {
      throw new Error(`Property photo rejected: the file exceeds the ${MAX_PHOTO_BYTES}-byte limit.`);
    }
    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.byteLength > MAX_PHOTO_BYTES) {
      throw new Error(`Property photo rejected: the file exceeds the ${MAX_PHOTO_BYTES}-byte limit.`);
    }
    return { data: buffer.toString("base64"), mimeType };
  }

  return {
    getProperty(propertyCode) {
      return request(`/api/hermes/properties/${encodeURIComponent(propertyCode)}`);
    },
    getPropertyPhoto(propertyCode) {
      return requestPhoto(`/api/hermes/properties/${encodeURIComponent(propertyCode)}/photo`);
    },
    searchProperties({ minArea, maxRent, limit, zone } = {}) {
      return request("/api/hermes/properties", {
        availability: "available",
        min_area: minArea,
        max_rent: maxRent,
        limit,
        zone,
      });
    },
    submitEnquiry(propertyCode, enquiry) {
      return request(`/api/hermes/properties/${encodeURIComponent(propertyCode)}/enquiries`, {}, { method: "POST", body: enquiry });
    },
  };
}

function toolResult(payload) {
  return {
    content: [{ type: "text", text: JSON.stringify(payload) }],
    structuredContent: payload,
  };
}

export async function resolveGetPropertyResult(client, propertyCode) {
  const payload = await client.getProperty(propertyCode);
  const content = [{ type: "text", text: JSON.stringify(payload) }];
  const photoUrl = payload?.property?.photo_url;
  if (photoUrl) {
    const photo = await client.getPropertyPhoto(propertyCode);
    content.push({ type: "image", data: photo.data, mimeType: photo.mimeType });
  }
  return { content, structuredContent: payload };
}

export function createHermesPropertyServer(clientFactory = createPropertyApiClient) {
  const server = new McpServer({
    name: "odoo-hermes-property-search",
    version: "1.0.0",
  });

  server.registerTool(
    "search_properties",
    {
      title: "Search public properties",
      description: `Search published available units for browsing (each result includes city, building name, a non-sensitive location hint and price in USD). Pass zone whenever the prospect gives any location reference (street, neighborhood, landmark or building name) — a bare zone/location query like a building name is enough to search, do not withhold the search waiting for a budget. Only pass max_rent/min_area if the prospect volunteers a budget or size spontaneously; never ask for them proactively. Once a prospect is discussing one specific unit (after get_property), do not call this again and do not offer other units in the same reply unless the prospect explicitly asks for alternatives or says the current unit does not work for them. ${REFRESH_BEFORE_ANSWERING_NOTICE}`,
      inputSchema: {
        zone: optionalZone(),
        min_area: optionalNonNegativeNumber("Minimum area in square meters. Only set this if the prospect volunteered it spontaneously; never ask for it."),
        max_rent: optionalNonNegativeNumber("Maximum monthly budget in USD. Only set this if the prospect volunteered it spontaneously; never ask for it."),
        limit: optionalLimit(),
      },
    },
    async ({ zone, min_area: minArea, max_rent: maxRent, limit }) => toolResult(await clientFactory().searchProperties({ zone, minArea, maxRent, limit })),
  );

  server.registerTool(
    "get_available_properties",
    {
      title: "Find available properties for a conversational budget, zone or size request",
      description: "Use only once the prospect has spontaneously stated a budget or a size requirement, together with a zone/location. Never ask the prospect for a budget or size to trigger this tool — if only a zone/location was given, use search_properties instead. Do not suggest other units once the prospect is already discussing one specific unit, unless they explicitly ask for alternatives.",
      inputSchema: {
        zone: optionalZone(),
        max_monthly_rent: optionalNonNegativeNumber("Prospect's stated monthly budget in USD, converted to a maximum monthly rent."),
        minimum_area: optionalNonNegativeNumber("Conversational area request converted to a minimum area in square meters."),
        limit: optionalLimit(),
      },
    },
    async ({ zone, max_monthly_rent: maxRent, minimum_area: minArea, limit }) => toolResult(await clientFactory().searchProperties({ zone, minArea, maxRent, limit })),
  );

  server.registerTool(
    "submit_property_enquiry",
    {
      title: "Submit a consented commercial-property enquiry",
      description: "Create a manager-reviewed, non-binding visit enquiry. Never use this without explicit consent; it never reserves a unit or creates a lease. Never ask the prospect for their monthly budget to submit this enquiry — budget is optional and should only be passed if the prospect already volunteered it earlier in the conversation.",
      inputSchema: {
        property_code: z.string().trim().min(1).max(128),
        name: z.string().trim().min(1).max(128),
        phone: z.string().trim().min(3).max(64),
        email: z.string().trim().regex(SIMPLE_EMAIL_PATTERN).max(254).optional(),
        company_name: z.string().trim().max(256).optional(),
        business_activity: z.string().trim().max(256).optional(),
        desired_start_date: z.string().date().optional(),
        budget: z.number().finite().nonnegative().optional().describe("The prospect's stated monthly budget in USD, only if volunteered spontaneously earlier in the conversation. Never ask for it."),
        consent: z.literal(true),
        visit_requested: z.boolean().optional(),
        message: z.string().trim().max(2000).optional(),
        channel: z.string().trim().max(128).optional(),
      },
    },
    async ({ property_code: propertyCode, ...enquiry }) => toolResult(await clientFactory().submitEnquiry(propertyCode, enquiry)),
  );

  server.registerTool(
    "get_property",
    {
      title: "Get a public property listing",
      description: `Get the public details for one published available unit by its property code returned from a search, including its price in USD, photo_url and virtual_tour_url. The photo is delivered as a native image attachment in this reply when available; always share it along with the virtual_tour_url digital-visit link, then ask if the prospect wants to request a physical visit (use submit_property_enquiry with visit_requested). Do not mention or suggest other units in this reply unless the prospect explicitly asks for alternatives. ${REFRESH_BEFORE_ANSWERING_NOTICE}`,
      inputSchema: {
        property_code: z.string().trim().min(1).max(128).describe("Public property code returned by a property search."),
      },
    },
    async ({ property_code: propertyCode }) => resolveGetPropertyResult(clientFactory(), propertyCode),
  );

  server.registerTool(
    "get_property_photo",
    {
      title: "Get or refresh a unit's photo",
      description: "MUST call this tool whenever the prospect asks whether a unit has a photo/foto or asks to see it, even if get_property was already called earlier in this conversation and even if the history already contains a photo or a 'no photo' answer. This always re-queries the current property record first, so it reflects a photo that was added, removed or changed since the last reply — never answer a photo question from conversation history alone. Returns the photo as a native image attachment when the unit currently has one; if it currently has none, returns the current property details as text only, without inventing or assuming a photo exists.",
      inputSchema: {
        property_code: z.string().trim().min(1).max(128).describe("Public property code returned by a property search."),
      },
    },
    async ({ property_code: propertyCode }) => resolveGetPropertyResult(clientFactory(), propertyCode),
  );

  return server;
}

export async function startServer() {
  const server = createHermesPropertyServer();
  await server.connect(new StdioServerTransport());
}

const invokedFile = process.argv[1] && path.resolve(process.argv[1]);
if (invokedFile === fileURLToPath(import.meta.url)) {
  startServer().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
