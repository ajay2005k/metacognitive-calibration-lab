import { describe, it, expect } from "vitest";
import { runInNewContext } from "node:vm";
import template from "../../deploy/aws/cloudformation.json";

const authorization = "Basic aW5zdHJ1Y3Rvcjp0ZXN0";
const source = template.Resources.AccessGate.Properties.FunctionCode[
  "Fn::Sub"
].replace("${AuthHeader}", authorization);
const handler = runInNewContext(`${source}; handler`);

describe("CloudFront deployment access gate", () => {
  it("challenges anonymous requests without exposing application data", () => {
    const result = handler({ request: { uri: "/api/export", headers: {} } });
    expect(result.statusCode).toBe(401);
    expect(result.headers["www-authenticate"].value).toContain("Basic");
    expect(result.headers["cache-control"].value).toBe("no-store");
  });
  it("rejects an incorrect credential", () => {
    expect(
      handler({
        request: { headers: { authorization: { value: "Basic wrong" } } },
      }).statusCode,
    ).toBe(401);
  });
  it("preserves authenticated API requests and removes credentials before forwarding", () => {
    const result = handler({
      request: {
        uri: "/api/sessions",
        method: "POST",
        querystring: {},
        headers: {
          authorization: { value: authorization },
          "content-type": { value: "application/json" },
        },
        body: { data: "trial" },
      },
    });
    expect(result.uri).toBe("/api/sessions");
    expect(result.method).toBe("POST");
    expect(result.body.data).toBe("trial");
    expect(result.headers.authorization).toBeUndefined();
    expect(result.headers["content-type"].value).toBe("application/json");
  });
});
