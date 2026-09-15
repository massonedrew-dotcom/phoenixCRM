import { createReadStream, existsSync } from "node:fs";
import type { ServerResponse } from "node:http";
import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API_TARGET = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";
// Development only: emulates nginx's internal media location, which serves the file
// named by the API's X-Accel-Redirect header. Production uses nginx itself.
const DEV_MEDIA_ROOT = process.env.VITE_DEV_MEDIA_ROOT;

function serveAccelRedirect(accelPath: string, contentType: string, res: ServerResponse): void {
  const relative = accelPath.replace(/^\/internal-media\//, "");
  if (!DEV_MEDIA_ROOT || relative.includes("..")) {
    res.statusCode = 404;
    res.end();
    return;
  }
  const file = resolve(DEV_MEDIA_ROOT, relative);
  if (!existsSync(file)) {
    res.statusCode = 404;
    res.end();
    return;
  }
  res.statusCode = 200;
  res.setHeader("Content-Type", contentType);
  createReadStream(file).pipe(res);
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: false,
        selfHandleResponse: true,
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes, _req, res) => {
            const accel = proxyRes.headers["x-accel-redirect"];
            if (typeof accel === "string") {
              proxyRes.resume();
              serveAccelRedirect(accel, proxyRes.headers["content-type"] ?? "", res);
              return;
            }
            res.writeHead(proxyRes.statusCode ?? 502, proxyRes.headers);
            proxyRes.pipe(res);
          });
        },
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
