import { defineConfig } from "vitest/config";
export default defineConfig({
  test: { include: ["tests_visible/**/*.test.ts", "tests_hidden/**/*.test.ts"] },
});
