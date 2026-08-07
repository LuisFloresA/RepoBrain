// Enmascarado de secretos en el visor de código.
// Preserva el número de líneas (solo se sustituyen subcadenas dentro de una
// misma línea), de modo que la línea resaltada siga siendo la correcta.

const PATTERNS: RegExp[] = [
  // Claves OpenAI / Anthropic / Gemini: sk-, sk-ant-, AIza..., ghp_...
  /sk-(?:ant-)?[A-Za-z0-9_-]{16,}/g,
  // AWS access key
  /AKIA[0-9A-Z]{16}/g,
  // Tokens JWT / passthrough de Bearer
  /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,
  // GitHub / npm / gitlab tokens
  /(?:ghp_|gho_|ghu_|ghs_|ghr_|npm_|glpat-)[A-Za-z0-9]{16,}/g,
  // Password / secret / token / api_key / apikey = "valor"
  /\b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret)\b\s*[:=]\s*['"]?[^\s'";,]+/gi,
  // Claves privadas
  /-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----/g,
];

function maskMatch(match: string): string {
  return match
    .split("\n")
    .map((line) => {
      const sepMatch = /[:=]/.exec(line);
      if (sepMatch) {
        // Conserva el nombre de la clave (p. ej. "password=") y enmascara el valor.
        const head = line.slice(0, sepMatch.index + 1);
        const rest = line.slice(sepMatch.index + 1).trimEnd();
        return `${head}${"*".repeat(Math.min(12, rest.length) || 1)}`;
      }
      return "*".repeat(Math.min(16, line.length) || 1);
    })
    .join("\n");
}

export function maskSecrets(content: string): string {
  let masked = content;
  for (const pattern of PATTERNS) {
    masked = masked.replace(pattern, maskMatch);
  }
  return masked;
}
