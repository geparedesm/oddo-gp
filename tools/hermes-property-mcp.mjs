import path from "node:path";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const DEFAULT_API_URL = "http://127.0.0.1:8069";
const MAX_LIMIT = 50;
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

  return {
    getProperty(propertyCode) {
      return request(`/api/hermes/properties/${encodeURIComponent(propertyCode)}`);
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

export function createHermesPropertyServer(clientFactory = createPropertyApiClient) {
  const server = new McpServer({
    name: "odoo-hermes-property-search",
    version: "1.0.0",
  });

  server.registerTool(
    "search_properties",
    {
      title: "Search public properties",
      description: "Search published available units for browsing (each result includes city, building name, a non-sensitive location hint and price in USD). Before calling this, always ask the prospect for their desired zone/location and their monthly budget, and pass them as zone/max_rent — never search blind. Once a prospect is discussing one specific unit (after get_property), do not call this again and do not offer other units in the same reply unless the prospect explicitly asks for alternatives or says the current unit does not work for them.",
      inputSchema: {
        zone: optionalZone(),
        min_area: optionalNonNegativeNumber("Minimum area in square meters. Only set this if the prospect volunteered it."),
        max_rent: optionalNonNegativeNumber("Maximum monthly budget in USD. Always ask the prospect for this before searching."),
        limit: optionalLimit(),
      },
    },
    async ({ zone, min_area: minArea, max_rent: maxRent, limit }) => toolResult(await clientFactory().searchProperties({ zone, minArea, maxRent, limit })),
  );

  server.registerTool(
    "get_available_properties",
    {
      title: "Find available properties for a conversational budget, zone or size request",
      description: "Use once the prospect has stated a zone/location and a budget (always ask for both before calling search_properties/this tool) or a size requirement. Do not suggest other units once the prospect is already discussing one specific unit, unless they explicitly ask for alternatives.",
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
      description: "Create a manager-reviewed, non-binding visit enquiry. Never use this without explicit consent; it never reserves a unit or creates a lease. Always ask the prospect's monthly budget in USD beforehand and pass it as budget, even if they already said no to a physical visit — it is recorded for managers to see stated willingness to pay against the unit's price.",
      inputSchema: {
        property_code: z.string().trim().min(1).max(128),
        name: z.string().trim().min(1).max(128),
        phone: z.string().trim().min(3).max(64),
        email: z.string().trim().regex(SIMPLE_EMAIL_PATTERN).max(254).optional(),
        company_name: z.string().trim().max(256).optional(),
        business_activity: z.string().trim().max(256).optional(),
        desired_start_date: z.string().date().optional(),
        budget: z.number().finite().nonnegative().optional().describe("The prospect's stated monthly budget in USD. Always ask for this."),
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
      description: "Get the public details for one published available unit by its property code returned from a search, including its price in USD, photo_url and virtual_tour_url. Always share the photo (fetch photo_url) and the virtual_tour_url digital-visit link in the same reply, then ask if the prospect wants to request a physical visit (use submit_property_enquiry with visit_requested). Do not mention or suggest other units in this reply unless the prospect explicitly asks for alternatives.",
      inputSchema: {
        property_code: z.string().trim().min(1).max(128).describe("Public property code returned by a property search."),
      },
    },
    async ({ property_code: propertyCode }) => toolResult(await clientFactory().getProperty(propertyCode)),
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
