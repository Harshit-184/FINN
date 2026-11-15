import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "FINN", short_name: "FINN", start_url: "/", display: "standalone",
    background_color: "#0e1620", theme_color: "#0e1620",
    description: "Portfolio brief and filing research for Indian equities.",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
