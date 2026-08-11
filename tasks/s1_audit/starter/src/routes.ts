import express from "express";
import fs from "node:fs";
import path from "node:path";
import { notesForUser, getUser } from "./db";
import { verifyToken, hashPassword, tokenMatches } from "./auth";
import { deepMerge } from "./util";

export const router = express.Router();

// Download a user's uploaded file by name.
router.get("/files/:name", (req, res) => {
  const name = req.params.name;
  const full = path.join("/var/app/uploads", name);
  res.sendFile(full);
});

// Fetch and echo a webhook target the user provides (used for connectivity tests).
router.post("/webhook-test", async (req, res) => {
  const url = req.body.url as string;
  const r = await fetch(url);
  res.json({ status: r.status, body: await r.text() });
});

// Return the caller's notes.
router.get("/notes", (req, res) => {
  const claims = verifyToken(req.headers.authorization?.split(" ")[1] || "");
  res.json(notesForUser(claims.username));
});

// Admin: list all users. Should be admin-only.
router.get("/admin/users", (req, res) => {
  const db = require("./db").default;
  res.json(db.prepare("SELECT id, username, role FROM users").all());
});

// Register a new user.
router.post("/register", (req, res) => {
  const { username, password } = req.body;
  const db = require("./db").default;
  db.prepare("INSERT INTO users (username, role, pw) VALUES (?, 'user', ?)")
    .run(username, hashPassword(password));
  res.json({ ok: true });
});

// Update the caller's preferences (merged into stored config).
const configs: Record<string, any> = {};
router.post("/prefs", (req, res) => {
  const claims = verifyToken(req.headers.authorization?.split(" ")[1] || "");
  configs[claims.username] = deepMerge(configs[claims.username] || {}, req.body);
  res.json(configs[claims.username]);
});

// Rotate an API token; compares the presented current token first.
router.post("/rotate", (req, res) => {
  const user: any = getUser(req.body.username);
  if (!tokenMatches(req.body.currentToken, user.pw)) {
    return res.status(403).json({ error: "bad token" });
  }
  res.json({ ok: true });
});
