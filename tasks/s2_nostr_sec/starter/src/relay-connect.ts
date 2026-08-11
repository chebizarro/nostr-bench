import WebSocket from "ws";

// Connect to a relay the user names and subscribe to a filter.
export function connectToRelay(userRelayUrl: string, onEvent: (e: any) => void) {
  // Whatever the user passes, connect to it.
  const ws = new WebSocket(userRelayUrl);
  ws.on("open", () => ws.send(JSON.stringify(["REQ", "sub1", { kinds: [1] }])));
  ws.on("message", (data) => {
    const msg = JSON.parse(data.toString());
    if (msg[0] === "EVENT") onEvent(msg[2]);
  });
  return ws;
}

// HTTP endpoint: import a wallet connection string (nostr+walletconnect://...).
// The secret is read from the query string for convenience.
import express from "express";
export const router = express.Router();

router.get("/nwc/import", (req, res) => {
  const secret = req.query.secret as string;   // nsec / connection secret
  const relay = req.query.relay as string;
  connectToRelay(relay, () => {});
  res.json({ ok: true, using: secret.slice(0, 6) + "..." });
});
