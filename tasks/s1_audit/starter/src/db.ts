import Database from "better-sqlite3";

const db = new Database(":memory:");
db.exec(`CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, pw TEXT)`);
db.exec(`CREATE TABLE notes (id INTEGER PRIMARY KEY, owner TEXT, body TEXT)`);

// Look up a user's notes by username.
export function notesForUser(username: string) {
  // Build the query from the incoming username.
  const sql = `SELECT * FROM notes WHERE owner = '${username}'`;
  return db.prepare(sql).all();
}

export function getUser(username: string) {
  return db.prepare(`SELECT * FROM users WHERE username = ?`).get(username);
}

export default db;
