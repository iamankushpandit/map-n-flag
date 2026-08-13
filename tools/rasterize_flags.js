/*
 * Rasterises flag SVGs to raw RGBA at the target size.
 *
 *   node tools/rasterize_flags.js <svgDir> <outDir> <W> <H> <codesJson> [prefix]
 *
 * Output: <outDir>/<code>.rgba, W*H*4 bytes, top-left origin.
 *
 * The optional `prefix` argument is prepended to each code when constructing
 * the SVG filename. For country flags prefix is empty (code "FR" -> "fr.svg").
 * For US state flags prefix is "us-" (code "CA" -> "us-ca.svg").
 *
 * Alpha is deliberately preserved. A few flags (Nepal most notably) are not
 * rectangular, and an indexed palette can hold a transparent entry for free,
 * so they end up looking correct on any UI background instead of sitting in a
 * black or white box.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const [svgDir, outDir, wArg, hArg, codesJson, prefix] = process.argv.slice(2);
const W = parseInt(wArg, 10);
const H = parseInt(hArg, 10);
const codes = JSON.parse(fs.readFileSync(codesJson, "utf8"));
const filePrefix = prefix || "";

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  let done = 0;
  const missing = [];

  for (const code of codes) {
    // Try lowercase first (flag-icons convention), then uppercase prefix
    // (region-flags uses "US-CA.svg"), then original case.
    const candidates = [
      `${filePrefix}${code.toLowerCase()}.svg`,
      `${filePrefix.toUpperCase()}${code.toUpperCase()}.svg`,
      `${filePrefix}${code}.svg`,
    ];
    const svg = candidates.map(f => path.join(svgDir, f)).find(fs.existsSync);
    if (!svg) {
      missing.push(code);
      continue;
    }

    // Try progressively lower densities if the SVG is too large at high
    // density.  flag-icons SVGs are small and render fine at 900; region-flags
    // SVGs can be very large and need a lower density.
    let buf = null;
    for (const density of [900, 300, 150, 72]) {
      try {
        buf = await sharp(svg, { density })
          .resize(W, H, { fit: "fill", kernel: "lanczos3" })
          .ensureAlpha()
          .raw()
          .toBuffer();
        break;
      } catch (e) {
        if (density === 72) throw e;
      }
    }

    if (!buf || buf.length !== W * H * 4) {
      throw new Error(`${code}: expected ${W * H * 4} bytes, got ${buf ? buf.length : 0}`);
    }
    fs.writeFileSync(path.join(outDir, `${code}.rgba`), buf);
    done++;
  }

  console.log(JSON.stringify({ rasterised: done, missing }));
})().catch((e) => {
  console.error("rasterize_flags failed:", e.message);
  process.exit(1);
});
