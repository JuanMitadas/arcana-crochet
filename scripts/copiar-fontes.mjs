// Copies the fonts (self-hosted because of the CSP) from node_modules to static/fonts.
import { copyFileSync, mkdirSync } from "node:fs";

const destino = "static/fonts";
mkdirSync(destino, { recursive: true });
const arquivos = {
  "@fontsource-variable/fraunces/files/fraunces-latin-full-normal.woff2": "fraunces.woff2",
  "@fontsource-variable/fraunces/files/fraunces-latin-full-italic.woff2": "fraunces-italic.woff2",
  "@fontsource-variable/montserrat/files/montserrat-latin-wght-normal.woff2": "montserrat.woff2",
  "@fontsource-variable/montserrat/files/montserrat-latin-wght-italic.woff2": "montserrat-italic.woff2",
};
for (const [origem, nome] of Object.entries(arquivos)) {
  copyFileSync(`node_modules/${origem}`, `${destino}/${nome}`);
  console.log(`static/fonts/${nome}`);
}
