import { describe, expect, it } from "vitest";
import { maskSecrets } from "../src/lib/mask";

describe("maskSecrets", () => {
  it("enmascara claves OpenAI sk-...", () => {
    const out = maskSecrets("const key = 'sk-proj-abc123XYZ-abcdefgh'");
    expect(out).not.toMatch(/sk-[A-Za-z0-9_-]{16,}/);
    expect(out).toContain("*");
  });

  it("enmascara access keys AWS", () => {
    expect(maskSecrets("AKIAIOSFODNN7EXAMPLE")).not.toContain("AKIAIOSFODNN7");
  });

  it("enmascara password=... conservando el nombre de la clave", () => {
    const out = maskSecrets("password = supersecret123\nuser = admin");
    expect(out).toMatch(/password =\*+/);
    expect(out).not.toContain("supersecret123");
    expect(out).toContain("user = admin");
  });

  it("enmascara tokens de acceso ghp_...", () => {
    expect(maskSecrets("token: ghp_1234567890abcdefghij")).not.toContain("ghp_");
  });

  it("enmascara bloques de clave privada preservando las líneas", () => {
    const block =
      "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkq\n-----END PRIVATE KEY-----\ncode()";
    const out = maskSecrets(block);
    expect(out).toContain("MIIEvQIBADANBgkq".length > 0 ? "*" : "");
    expect(out).not.toContain("MIIEvQIBADANBgkq");
    expect(out.split("\n").length).toBe(4); // mismo número de líneas
  });

  it("no altera código sin secretos", () => {
    const code = "def verify_jwt(token):\n    return token\n";
    expect(maskSecrets(code)).toBe(code);
  });
});
