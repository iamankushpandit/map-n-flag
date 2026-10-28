/*
 * Rasterises the ASL hand SVGs to large single-channel ink masks.
 *
 *   node tools/rasterize_signs.js <svgDir> <outDir> <height> <lettersJson>
 *
 * Output: <outDir>/<letter>.png, greyscale, white ink on black, <height> px
 * tall with the source's aspect ratio. Cropping, thickening and the final
 * downscale happen in build.py, where the rest of the image pipeline lives;
 * this script only does what Python cannot without a native SVG library.
 *
 * The source SVGs are black line art on a transparent page, so the alpha
 * channel IS the drawing. It is extracted rather than the luminance, which
 * would also pick up whatever colour the transparent pixels happen to carry.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const [svgDir, outDir, hArg, lettersJson] = process.argv.slice(2);
const H = parseInt(hArg, 10);
const letters = JSON.parse(fs.readFileSync(lettersJson, "utf8"));

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  let done = 0;
  const missing = [];

  for (const letter of letters) {
    const svg = path.join(svgDir, `${letter.toLowerCase()}.svg`);
    if (!fs.existsSync(svg)) {
      missing.push(letter);
      continue;
    }
    await sharp(svg, { density: 300 })
      .resize({ height: H, kernel: "lanczos3" })
      .ensureAlpha()
      .extractChannel("alpha")
      .png()
      .toFile(path.join(outDir, `${letter}.png`));
    done++;
  }

  console.log(JSON.stringify({ rasterised: done, missing }));
})().catch((e) => {
  console.error("rasterize_signs failed:", e.message);
  process.exit(1);
});
