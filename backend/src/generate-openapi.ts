import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

process.env.DATABASE_URL ??= "postgres://placeholder:placeholder@localhost:5432/pahlen_monitor";

const { createApp } = await import("./app.js");

const app = createApp();
const document = app.getOpenAPIDocument({
  openapi: "3.0.0",
  info: {
    title: "Pahlen Monitor API",
    version: "1.0.0",
  },
});

const outputPath = resolve(process.cwd(), "openapi.json");
writeFileSync(outputPath, `${JSON.stringify(document, null, 2)}\n`, "utf-8");
console.log(`Wrote ${outputPath}`);
