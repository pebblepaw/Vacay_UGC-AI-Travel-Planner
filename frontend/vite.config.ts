import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

const frontendRoot = __dirname;
const defaultEnvDir = path.resolve(frontendRoot, "..");
const envDir = process.env.ENV_FILE ? path.dirname(process.env.ENV_FILE) : defaultEnvDir;

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  envDir,
  envPrefix: ["VITE_", "MAPBOX_"],
  server: {
    host: "::",
    port: 8080,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
    },
    hmr: {
      overlay: false,
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
