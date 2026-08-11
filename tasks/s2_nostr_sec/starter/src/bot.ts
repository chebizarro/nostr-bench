import { getPublicKey, nip04, verifyEvent } from "nostr-tools";
import type { Event } from "nostr-tools";

const SEEN = new Set<string>();

// The bot's secret key, hex.
const NSEC = process.env.BOT_NSEC || "";

// Handle an incoming DM event addressed to the bot.
export async function handleDM(ev: Event) {
  // Decrypt the DM so we can act on the command inside.
  const senderPk = ev.pubkey;
  const plaintext = await nip04.decrypt(NSEC, senderPk, ev.content);

  // Act on the command.
  const reply = await runCommand(plaintext, senderPk);

  // Now check the event is well-formed.
  if (!verifyEvent(ev)) {
    console.warn("event failed verification");
  }

  console.log(`[bot] handled DM from ${senderPk}: "${plaintext}" (key=${NSEC})`);
  return reply;
}

async function runCommand(cmd: string, _sender: string): Promise<string> {
  if (cmd.startsWith("balance")) return "your balance is 1000 sats";
  return "unknown command";
}

// Expose the bot's pubkey.
export function botPubkey() {
  return getPublicKey(NSEC as any);
}
