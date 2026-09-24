/**
 * apiError.test.ts — tests for shared/api/apiError.ts
 * DOC 3 C3 Done When: apiError mapping tested.
 */

import { describe, it, expect } from "vitest";
import { apiError } from "../apiError";


describe("apiError()", () => {
  it("maps an Error to network_error", () => {
    const result = apiError(new Error("fetch failed"));
    expect(result.code).toBe("network_error");
    expect(result.message).toBe("fetch failed");
  });

  it("maps a server { code, message } body", () => {
    const result = apiError({ code: "not_found", message: "Alert not found." });
    expect(result.code).toBe("not_found");
    expect(result.message).toBe("Alert not found.");
  });

  it("maps a 422 Pydantic validation error", () => {
    const result = apiError({
      detail: [
        { loc: ["body", "amount_paise"], msg: "value is not a valid integer", type: "type_error.integer" },
      ],
    });
    expect(result.code).toBe("validation_error");
    expect(result.fields).toMatchObject({ "amount_paise": "value is not a valid integer" });
  });

  it("maps a string detail body", () => {
    const result = apiError({ detail: "Internal Server Error" });
    expect(result.code).toBe("error");
    expect(result.message).toBe("Internal Server Error");
  });

  it("maps unknown input to unknown", () => {
    const result = apiError(null);
    expect(result.code).toBe("unknown");
  });
});
