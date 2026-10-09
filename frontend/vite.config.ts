import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import type { Plugin } from "vite";

// Inline the (single, ~10 kB gzipped) stylesheet into index.html: one round trip less before the first paint.
function inlineCss(): Plugin {
  return {
    name: "inline-css",
    apply: "build",
    enforce: "post",
    generateBundle(_, bundle) {
      const html = Object.values(bundle).find((f) => f.fileName === "index.html");
      if (!html || html.type !== "asset") return;
      let src = String(html.source);
      for (const f of Object.values(bundle)) {
        if (f.type === "asset" && f.fileName.endsWith(".css")) {
          const tag = new RegExp(`<link rel="stylesheet"[^>]*href="[^"]*${f.fileName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"[^>]*>`);
          if (tag.test(src)) {
            // Body fonts (IBM Plex) use font-display: optional, so text is laid out once and never reflows when a
            // font arrives late; on localhost they load inside the 100 ms block period. The display face keeps swap.
            const css = String(f.source).replace(/@font-face\{[^}]*\}/g, (face) =>
              face.includes("IBM Plex") ? face.replace("font-display:swap", "font-display:optional") : face);
            src = src.replace(tag, () => `<style>${css}</style>`);
            // the file stays too: lazy chunks preload it by name
          }
        }
      }
      // Preload the body font so the app shell and the React page paint with the same face.
      const font = Object.values(bundle).find((f) => /ibm-plex-sans-latin-400-normal.*\.woff2$/.test(f.fileName));
      if (font) src = src.replace("</title>", `</title>\n    <link rel="preload" href="/static/ui/${font.fileName}" as="font" type="font/woff2" crossorigin>`);
      // Preload the chunk of the page being opened (no request waterfall after the main bundle).
      const routes: Record<string, string> = { Compare: "/compare", Suite: "/suite", Results: "/results", How: "/how",
        History: "/history", ImageMode: "/image", Status: "/status" };
      const map: Record<string, string> = {};
      for (const f of Object.values(bundle)) {
        const page = f.type === "chunk" && f.isDynamicEntry ? f.name : null;
        if (page && routes[page]) map[routes[page]] = `/static/ui/${f.fileName}`;
      }
      src = src.replace("</head>", `<script>(function(){var u=${JSON.stringify(map)}[location.pathname];if(u){var l=document.createElement("link");l.rel="modulepreload";l.href=u;document.head.appendChild(l);}})();</script>\n  </head>`);
      html.source = src;
    },
  };
}

// Built into the folder FastAPI serves (app/static/ui), so `uvicorn app.api:app` runs the UI without Node.
export default defineConfig({
  base: "/static/ui/",
  plugins: [react(), tailwindcss(), inlineCss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: {
    outDir: "../backend/app/static/ui",
    emptyOutDir: true,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
