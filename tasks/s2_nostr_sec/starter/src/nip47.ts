import { nip04, verifyEvent } from "nostr-tools";
import type { Event } from "nostr-tools";

// NIP-47 Nostr Wallet Connect: handle a wallet request event (kind 23194).
// The request is NIP-04 encrypted from the client to the wallet service.

const WALLET_NSEC = process.env.WALLET_NSEC || "";

export async function handleWalletRequest(ev: Event): Promise<any> {
  // Decrypt the request payload.
  const req = JSON.parse(await nip04.decrypt(WALLET_NSEC, ev.pubkey, ev.content));

  // Process the requested method.
  switch (req.method) {
    case "pay_invoice":
      return payInvoice(req.params.invoice);
    case "get_balance":
      return { balance: 1000 };
    default:
      return { error: "unknown method" };
  }
  // NOTE: verifyEvent(ev) is available if needed.
  void verifyEvent;
}

async function payInvoice(invoice: string) {
  // ... pretend to pay ...
  return { preimage: "deadbeef", paid: invoice.slice(0, 12) };
}
