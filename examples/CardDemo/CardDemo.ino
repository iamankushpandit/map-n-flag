/*
 * map-n-flag -- playing card demo (no LVGL).
 *
 * Shuffles the deck, deals a five-card hand across a 320x240 ESP32 "Cheap
 * Yellow Display" (ESP32-2432S028R, ILI9341), then deals again every three
 * seconds. The last slot shows the card back.
 *
 * The point of interest is the background colour: card corners are
 * transparent, so mnf_row_rgb565() is given the felt colour and the rounded
 * corners composite onto it instead of showing a white box.
 *
 * ---------------------------------------------------------------------------
 * PlatformIO
 * ---------------------------------------------------------------------------
 *   lib_deps =
 *       bodmer/TFT_eSPI@^2.5.43
 *       https://github.com/iamankushpandit/map-n-flag.git
 *   board_build.partitions = huge_app.csv
 * ---------------------------------------------------------------------------
 */

#include <Arduino.h>
#include <TFT_eSPI.h>

#include "map_n_flag.h"

static TFT_eSPI tft = TFT_eSPI();

#define HAND_SIZE  5

/* One decoded row of a card. 48 pixels, so 96 bytes of scratch. */
static uint16_t row_buf[MNF_CARD_WIDTH];

/* The shuffled deck, as indices into the sorted card table. */
static uint8_t order[52];

static uint16_t felt;

static void draw_card(const mnf_img_t *img, int16_t x, int16_t y)
{
    if (img == NULL) return;

    tft.startWrite();
    for (uint16_t yy = 0; yy < img->h; yy++) {
        /* Passing `felt` as the background is what makes the transparent
         * corners land on the table instead of on white. */
        mnf_row_rgb565(img, yy, row_buf, felt);
        tft.setAddrWindow(x, y + yy, img->w, 1);
        tft.pushPixels(row_buf, img->w);
    }
    tft.endWrite();
}

static void shuffle(void)
{
    const uint8_t n = (uint8_t)mnf_card_count();
    for (uint8_t i = 0; i < n; i++) order[i] = i;

    for (uint8_t i = n - 1; i > 0; i--) {       // Fisher-Yates
        const uint8_t j = (uint8_t)random(i + 1);
        const uint8_t t = order[i];
        order[i] = order[j];
        order[j] = t;
    }
}

static void deal(void)
{
    shuffle();
    tft.fillScreen(felt);

    /* HAND_SIZE cards plus the back, spread evenly. */
    const int16_t slots = HAND_SIZE + 1;
    const int16_t pitch = 320 / slots;
    const int16_t x0 = (pitch - MNF_CARD_WIDTH) / 2;
    const int16_t y = 70;

    for (int16_t i = 0; i < HAND_SIZE; i++) {
        const mnf_card_t *c = mnf_card_at(order[i]);
        if (c == NULL) continue;

        draw_card(c->img, x0 + i * pitch, y);

        tft.setTextColor(mnf_card_is_red(c) ? TFT_RED : TFT_WHITE, felt);
        tft.setTextDatum(TC_DATUM);
        tft.drawString(c->code, x0 + i * pitch + MNF_CARD_WIDTH / 2,
                       y + MNF_CARD_HEIGHT + 6, 2);

        Serial.printf("  %s (%s), rank %u suit %u\n",
                      c->code, c->name, c->rank, c->suit);
    }

    draw_card(mnf_card_back(), x0 + HAND_SIZE * pitch, y);

    tft.setTextColor(TFT_WHITE, felt);
    tft.setTextDatum(TC_DATUM);
    tft.drawString("map-n-flag deck", 160, 16, 4);
}

void setup(void)
{
    Serial.begin(115200);
    randomSeed(esp_random());

    tft.init();
    tft.setRotation(1);          // landscape 320x240
    tft.setSwapBytes(true);      // if colours look inverted, flip this

    felt = mnf_rgb565(0x16, 0x5C, 0x3C);
    tft.fillScreen(felt);

#ifdef TFT_BL
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, HIGH);
#endif

    // --- lookup API smoke test over the serial monitor ---------------------
    Serial.printf("map-n-flag: %u cards\n", (unsigned)mnf_card_count());

    const mnf_card_t *as = mnf_card_find("as");    // lookup is case-insensitive
    if (as != NULL) {
        Serial.printf("AS -> %s, %ux%u\n", as->name, as->img->w, as->img->h);
    }
    const mnf_card_t *kh = mnf_card_by(13, MNF_SUIT_HEARTS);
    if (kh != NULL) Serial.printf("13 of hearts -> %s (%s)\n", kh->code, kh->name);
    if (mnf_card("XX") == NULL) Serial.println("unknown code returns NULL, good");

    deal();
}

void loop(void)
{
    static uint32_t last = 0;
    if (millis() - last >= 3000) {
        last = millis();
        deal();
    }
}
