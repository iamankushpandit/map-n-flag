/*
 * Rasterises flag-icons SVGs to raw RGBA at the target size.
 *
 *   node tools/rasterize_flags.js <svgDir> <outDir> <W> <H> <codesJson>
 *
 * Output: <outDir>/<code>.rgba, W*H*4 bytes, top-left origin.
 *
 * Alpha is deliberately preserved. A few flags (Nepal most notably) are not
 * rectangular, and an indexed palette can hold a transparent entry for free,
 * so they end up looking correct on any UI background instead of sitting in a
 * black or white box.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const [svgDir, outDir, wArg, hArg, codesJson] = process.argv.slice(2);
const W = parseInt(wArg, 10);
const H = parseInt(hArg, 10);
const codes = JSON.parse(fs.readFileSync(codesJson, "utf8"));

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  let done = 0;
  const missing = [];

  for (const code of codes) {
    const svg = path.join(svgDir, `${code.toLowerCase()}.svg`);
    if (!fs.existsSync(svg)) {
      missing.push(code);
      continue;
    }
    // High density first so fine details (coats of arms) are supersampled
    // before the Lanczos downscale, rather than rasterised straight to 80px.
    const buf = await sharp(svg, { density: 900 })
      .resize(W, H, { fit: "fill", kernel: "lanczos3" })
      .ensureAlpha()
      .raw()
      .toBuffer();

    if (buf.length !== W * H * 4) {
      throw new Error(`${code}: expected ${W * H * 4} bytes, got ${buf.length}`);
    }
    fs.writeFileSync(path.join(outDir, `${code}.rgba`), buf);
    done++;
  }

  console.log(JSON.stringify({ rasterised: done, missing }));
})().catch((e) => {
  console.error("rasterize_flags failed:", e.message);
  process.exit(1);
});
