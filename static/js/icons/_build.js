/* Gera static/js/icons.js a partir dos SVGs em static/js/icons/*.svg (Lucide, MIT).
   Rodar com `node static/js/icons/_build.js` sempre que adicionar/atualizar um ícone. */
const fs = require("fs");
const path = require("path");

const dir = __dirname;
const outFile = path.join(dir, "..", "icons.js");

const files = fs
  .readdirSync(dir)
  .filter((f) => f.endsWith(".svg"))
  .sort();

const entries = files.map((f) => {
  const name = f.replace(/\.svg$/, "");
  const raw = fs.readFileSync(path.join(dir, f), "utf8");
  const inner = raw
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/^[\s\S]*?<svg[^>]*>/, "")
    .replace(/<\/svg>\s*$/, "")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/> </g, "><");
  return `  "${name}": ${JSON.stringify(inner)}`;
});

const content = `/* Ícones inline (Lucide, MIT license: https://lucide.dev) — gerado por icons/_build.js, não editar à mão. */

const ICONS = {
${entries.join(",\n")}
};
`;

fs.writeFileSync(outFile, content, "utf8");
console.log(`Wrote ${outFile} with ${files.length} icons.`);
