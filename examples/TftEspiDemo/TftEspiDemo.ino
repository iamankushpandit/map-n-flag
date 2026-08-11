/*
 * map-n-flag -- TFT_eSPI demo (no LVGL).
 *
 * Draws a country's flag and outline side by side on a 320x240 ESP32 "Cheap
 * Yellow Display" (ESP32-2432S028R, ILI9341), cycling every two seconds.
 *
 * This is the path to use if your project talks to the display directly
 * instead of going through LVGL. The library core has no LVGL dependency.
 *
 * No game logic here -- this is purely a rendering smoke test.
 *
 * ---------------------------------------------------------------------------
 * PlatformIO
 * ---------------------------------------------------------------------------
 *   lib_deps =
 *       bodmer/TFT_eSPI@^2.5.43
 *       https://github.com/iamankushpandit/map-n-flag.git
 *   board_build.partitions = huge_app.csv
 *
 * The partition line matters: the default 4MB scheme gives the app only
 * 1.31 MB, which is less than the asset library alone.
 * ---------------------------------------------------------------------------
 */

#include <Arduino.h>
#include <TFT_eSPI.h>

#include "map_n_flag.h"

static TFT_eSPI tft = TFT_eSPI();

static const uint16_t BG = 0xFFFF;   // white

/* Scratch for one decoded row. The widest thing we ever draw is
 * max(MNF_FLAG_WIDTH, MNF_MAP_BOX) pixels, so this is under 200 bytes. */
#define MNF_MAX_W ((MNF_FLAG_WIDTH > MNF_MAP_BOX) ? MNF_FLAG_WIDTH : MNF_MAP_BOX)
static uint16_t row_buf[MNF_MAX_W];

/**
 * Blit an image row by row. Never allocates a framebuffer -- it decodes one
 * row at a time straight from flash into row_buf and pushes it.
 */
static void draw_image(const mnf_img_t *img, int16_t x, int16_t y, uint16_t bg)
{
    if (img == NULL) return;

    tft.startWrite();
    for (uint16_t yy = 0; yy < img->h; yy++) {
        mnf_row_rgb565(img, yy, row_buf, bg);
        tft.setAddrWindow(x, y + yy, img->w, 1);
        tft.pushPixels(row_buf, img->w);
    }
    tft.endWrite();
}

/**
 * Same, but recolours the silhouette at draw time. Map images store a 16-step
 * alpha ramp, so any ink colour works without regenerating the data.
 */
static void draw_image_tinted(const mnf_img_t *img, int16_t x, int16_t y,
                              uint16_t bg, uint16_t fg)
{
    if (img == NULL) return;

    tft.startWrite();
    for (uint16_t yy = 0; yy < img->h; yy++) {
        mnf_row_rgb565_tint(img, yy, row_buf, bg, fg);
        tft.setAddrWindow(x, y + yy, img->w, 1);
        tft.pushPixels(row_buf, img->w);
    }
    tft.endWrite();
}

static size_t current = 0;

static void show_next(void)
{
    const size_t n = mnf_count();

    for (size_t step = 0; step < n; step++) {
        current = (current + 1) % n;
        const mnf_country_t *c = mnf_at(current);

        // Four countries (FM, MH, PS, TV) have a flag but no map.
        if (c == NULL || !mnf_has_both(c->iso2)) continue;

        tft.fillScreen(BG);

        const mnf_img_t *flag = c->flag;
        const mnf_img_t *map  = c->map;

        // Flag on the left, vertically centred in the upper area.
        draw_image(flag, 30, 60 - flag->h / 2, BG);

        // Map on the right, tinted navy, centred in a MNF_MAP_BOX square.
        draw_image_tinted(map,
                          210 - map->w / 2,
                          130 - map->h / 2,
                          BG, tft.color565(0x1E, 0x3A, 0x8A));

        tft.setTextColor(tft.color565(0x1E, 0x3A, 0x8A), BG);
        tft.setTextDatum(BC_DATUM);
        tft.drawString(c->name, 160, 232, 4);

        tft.setTextColor(TFT_DARKGREY, BG);
        tft.setTextDatum(TC_DATUM);
        tft.drawString(c->iso2, 160, 6, 2);
        return;
    }
}

void setup(void)
{
    Serial.begin(115200);

    tft.init();
    tft.setRotation(1);          // landscape 320x240
    tft.setSwapBytes(true);      // if colours look inverted, flip this
    tft.fillScreen(BG);

#ifdef TFT_BL
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, HIGH);
#endif

    // --- lookup API smoke test over the serial monitor ---------------------
    Serial.printf("map-n-flag: %u countries\n", (unsigned)mnf_count());

    const mnf_country_t *fr = mnf_find("fr");    // lookup is case-insensitive
    if (fr != NULL) {
        Serial.printf("FR -> %s, flag %ux%u, map %ux%u\n",
                      fr->name,
                      fr->flag->w, fr->flag->h,
                      fr->map->w,  fr->map->h);
    }
    if (mnf_flag("ZZ") == NULL) Serial.println("unknown code returns NULL, good");
    if (mnf_map("PS") == NULL)  Serial.println("PS has a flag but no map, as expected");

    show_next();
}

void loop(void)
{
    static uint32_t last = 0;
    if (millis() - last >= 2000) {
        last = millis();
        show_next();
    }
}
