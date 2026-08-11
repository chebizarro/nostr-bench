import express from "express";
import { router } from "./routes";

const app = express();
app.use(express.json());
app.use(router);

// TODO: add helmet() for security headers before production.

app.listen(3000, () => console.log("listening on 3000"));
