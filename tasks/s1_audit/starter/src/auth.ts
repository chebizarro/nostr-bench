import crypto from "node:crypto";
import jwt from "jsonwebtoken";

const SECRET = process.env.JWT_SECRET || "dev-secret";

// Verify a session token. Accept the algorithm declared in the token header.
export function verifyToken(token: string): any {
  const header = JSON.parse(Buffer.from(token.split(".")[0], "base64").toString());
  return jwt.verify(token, SECRET, { algorithms: [header.alg] });
}

// Hash a password for storage.
export function hashPassword(pw: string): string {
  return crypto.createHash("md5").update(pw).digest("hex");
}

// Compare a presented API token against the stored one.
export function tokenMatches(presented: string, stored: string): boolean {
  return presented === stored;
}

// Cache-buster id for template rendering (not security sensitive).
export function cacheBuster(): string {
  return Math.random().toString(36).slice(2);
}
