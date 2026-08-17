import path from "node:path";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const DEFAULT_API_URL = "http://127.0.0.1:8069";
const MAX_LIMIT = 50;

function optionalNonNegativeNumber(description) {
  return z.number().finite().nonnegative().optional().describe(description);
}

function optionalLimit() {
  return z.number().int().min(1).max(MAX_LIMIT).optional().describe("Maximum number of properties to return (1-50). Defaults to 20.");
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
    searchProperties({ minArea, maxRent, limit } = {}) {
      return request("/api/hermes/properties", {
        availability: "available",
        min_area: minArea,
        max_rent: maxRent,
        limit,
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
      description: "Search published available properties. Use min_area for a minimum area in square meters and max_rent for a maximum monthly rent.",
      inputSchema: {
        min_area: optionalNonNegativeNumber("Minimum area in square meters."),
        max_rent: optionalNonNegativeNumber("Maximum monthly rent."),
        limit: optionalLimit(),
      },
    },
    async ({ min_area: minArea, max_rent: maxRent, limit }) => toolResult(await clientFactory().searchProperties({ minArea, maxRent, limit })),
  );

  server.registerTool(
    "get_available_properties",
    {
      title: "Find available properties for a conversational request",
      description: "Use for requests such as 'under 1200 per month' or 'at least 100 square meters'. Convert budget to max_monthly_rent and requested area to minimum_area before calling.",
      inputSchema: {
        max_monthly_rent: optionalNonNegativeNumber("Conversational budget converted to a maximum monthly rent."),
        minimum_area: optionalNonNegativeNumber("Conversational area request converted to a minimum area in square meters."),
        limit: optionalLimit(),
      },
    },
    async ({ max_monthly_rent: maxRent, minimum_area: minArea, limit }) => toolResult(await clientFactory().searchProperties({ minArea, maxRent, limit })),
  );

  server.registerTool(
    "submit_property_enquiry",
    {
      title: "Submit a consented commercial-property enquiry",
      description: "Create a manager-reviewed, non-binding visit enquiry. Never use this without explicit consent; it never reserves a unit or creates a lease.",
      inputSchema: {
        property_code: z.string().trim().min(1).max(128),
        name: z.string().trim().min(1).max(128),
        phone: z.string().trim().min(3).max(64),
        email: z.string().trim().email().max(254).optional(),
        company_name: z.string().trim().max(256).optional(),
        business_activity: z.string().trim().max(256).optional(),
        desired_start_date: z.string().date().optional(),
        consent: z.literal(true),
        visit_requested: z.boolean().optional(),
        message: z.string().trim().max(2000).optional(),
      },
    },
    async ({ property_code: propertyCode, ...enquiry }) => toolResult(await clientFactory().submitEnquiry(propertyCode, enquiry)),
  );

  server.registerTool(
    "get_property",
    {
      title: "Get a public property listing",
      description: "Get the public details for one published available property by its property code returned from a search.",
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
