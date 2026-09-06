import path from "node:path";
import * as dotenv from "@dotenvx/dotenvx";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

import fs from "node:fs";
import { execSync } from "node:child_process";

dotenv.config({ path: path.resolve(__dirname, ".env") });

const viteEnv = Object.keys(process.env)
  .filter((k) => k.startsWith("VITE_"))
  .reduce<Record<string, string>>((a, k) => {
    a[k] = process.env[k] ?? "";
    return a;
  }, {});

let commitHash = process.env.VITE_GIT_COMMIT_HASH || "";
if (!commitHash) {
  try {
    commitHash = execSync("git rev-parse --short HEAD", {
      cwd: path.resolve(__dirname, "../.."),
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
  } catch {
    // fallback
  }
}
if (!commitHash) {
  try {
    const commitFile = path.resolve(__dirname, "commit.json");
    if (fs.existsSync(commitFile)) {
      const commitData = JSON.parse(fs.readFileSync(commitFile, "utf-8"));
      commitHash = commitData.commitHash || "";
    }
  } catch {
    // fallback
  }
}
viteEnv.VITE_GIT_COMMIT_HASH = commitHash;

export default defineConfig(() => ({
  define: {
    "process.env": JSON.stringify(viteEnv),
  },
  build: {
    assetsInlineLimit: 4096,
  },
  plugins: [reactRouter(), tsconfigPaths({ projects: [path.resolve(__dirname, "tsconfig.json")] })],
  resolve: {
    alias: {
      // Next.js compatibility shims used within web
      "next/link": path.resolve(__dirname, "app/compat/next/link.tsx"),
      "next/navigation": path.resolve(__dirname, "app/compat/next/navigation.ts"),
      "next/script": path.resolve(__dirname, "app/compat/next/script.tsx"),
    },
    dedupe: ["react", "react-dom", "@headlessui/react"],
  },
  server: {
    host: "127.0.0.1",
    proxy: {
      // Mirror Caddy's production reverse proxy setup for local dev:
      // All requests go through Vite so relative redirects (e.g. /uploads/...)
      // resolve to the same origin and get proxied correctly.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: false, // preserve Host header for presigned URL signature consistency
      },
      "/auth": {
        target: "http://localhost:8000",
        changeOrigin: false,
      },
      "/uploads": {
        target: "http://localhost:9000",
        changeOrigin: false,
      },
    },
  },
  // No SSR-specific overrides needed; alias resolves to ESM build
}));
