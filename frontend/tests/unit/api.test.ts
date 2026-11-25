import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, errorMessage, request, setAccessToken } from "@/lib/api";

function json(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

describe("request", () => {
  it("sends the bearer token and If-Match, and unwraps the envelope", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(200, { data: { id: "p1" }, meta: { request_id: "r", page: null } }));
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("tok");
    const data = await api.patch<{ id: string }>("/projects/p1", { name: "x" }, 3);
    expect(data).toEqual({ id: "p1" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/projects\/p1$/);
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(init.headers["If-Match"]).toBe('"3"');
    expect(init.credentials).toBe("include");
  });

  it("turns problem details into ApiError with field errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json(422, {
          code: "validation_error",
          detail: "The request is invalid",
          errors: [{ field: "name", message: "Field required" }],
        }),
      ),
    );
    const err = await request("/projects", { method: "POST", body: {} }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.code).toBe("validation_error");
    expect(err.fieldError("name")).toBe("Field required");
    expect(errorMessage(err)).toBe("The request is invalid");
  });

  it("refreshes the session once on 401 and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { code: "unauthorized", detail: "Sign in" }))
      .mockResolvedValueOnce(
        json(200, { data: { access_token: "new", expires_in: 900, user: {} }, meta: { request_id: null, page: null } }),
      )
      .mockResolvedValueOnce(json(200, { data: ["ok"], meta: { request_id: null, page: null } }));
    vi.stubGlobal("fetch", fetchMock);
    const data = await api.get<string[]>("/projects");
    expect(data).toEqual(["ok"]);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/auth\/refresh$/);
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe("Bearer new");
  });

  it("returns undefined data for 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(api.delete("/projects/p1")).resolves.toBeUndefined();
  });

  it("explains network failures", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toMatch(/Cannot reach the server/);
  });
});
