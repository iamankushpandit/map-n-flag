/*
 * map-n-flag -- LVGL demo.
 *
 * Shows a country's flag and outline side by side on a 320x240 ESP32 "Cheap
 * Yellow Display", cycling every two seconds. Uses the optional LVGL adapter;
 * see TftEspiDemo for the no-LVGL path.
 *
 * Targets LVGL v8 (the display-driver calls below are v8 API). The library
 * itself supports v8 and v9 -- only this file's driver setup is v8-specific.
 *
 * ---------------------------------------------------------------------------
 * Why nothing here calls lv_img_set_zoom()
 * ---------------------------------------------------------------------------
 * These are 4-bit indexed images. LVGL v8's decoder handles indexed formats by
 * building a small palette in RAM and streaming pixels from flash line by line
 * -- it never sets `img_data`. In lv_draw_img.c, that line-by-line branch
 * ignores `zoom` and `angle`, so a zoom call silently does nothing.
 *
 * The rule: for indexed images, STORED SIZE == DISPLAYED SIZE. To show a
 * bigger flag, raise FLAG_W/FLAG_H in tools/config.py and regenerate.
 * ---------------------------------------------------------------------------
 */

#include <Arduino.h>
#include <lvgl.h>
#include <TFT_eSPI.h>

#include "map_n_flag.h"
#include "map_n_flag_lvgl.h"

static const uint16_t SCREEN_W = 320;
static const uint16_t SCREEN_H = 240;

static TFT_eSPI tft = TFT_eSPI();
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[SCREEN_W * 10];

static void disp_flush(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *pixels)
{
    const uint32_t w = area->x2 - area->x1 + 1;
    const uint32_t h = area->y2 - area->y1 + 1;

    tft.startWrite();
    tft.setAddrWindow(area->x1, area->y1, w, h);
    tft.pushColors((uint16_t *)pixels, w * h, true);
    tft.endWrite();

    lv_disp_flush_ready(disp);
}

static lv_obj_t *flag_img;
static lv_obj_t *map_img;
static lv_obj_t *name_label;
static lv_obj_t *code_label;

/* LVGL keeps the descriptor pointer, so these must outlive the widgets.
 * One slot per widget -- never share a slot between two visible images. */
static mnf_lv_dsc_t flag_slot;
static mnf_lv_dsc_t map_slot;

static size_t current = 0;

static void show_next(lv_timer_t *timer)
{
    LV_UNUSED(timer);

    const size_t n = mnf_count();
    for (size_t step = 0; step < n; step++) {
        current = (current + 1) % n;
        const mnf_country_t *c = mnf_at(current);

        // Four countries (FM, MH, PS, TV) have a flag but no map.
        if (c == NULL || !mnf_has_both(c->iso2)) continue;

        lv_img_set_src(flag_img, mnf_lv_bind(&flag_slot, c->flag));
        lv_img_set_src(map_img,  mnf_lv_bind(&map_slot,  c->map));
        lv_label_set_text(name_label, c->name);
        lv_label_set_text(code_label, c->iso2);
        return;
    }
}

static void build_ui(void)
{
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0xF4F4F8), LV_PART_MAIN);

    // Flag on the left, at its native size.
    flag_img = lv_img_create(scr);
    lv_obj_align(flag_img, LV_ALIGN_LEFT_MID, 28, -8);

    // Map on the right. Each outline is cropped to its own bounding box, so
    // its size varies up to MNF_MAP_BOX; aligning the object centres it.
    map_img = lv_img_create(scr);
    lv_obj_align(map_img, LV_ALIGN_RIGHT_MID, -40, -8);

    name_label = lv_label_create(scr);
    lv_obj_set_style_text_color(name_label, lv_color_hex(0x1E3A8A), LV_PART_MAIN);
    lv_obj_align(name_label, LV_ALIGN_BOTTOM_MID, 0, -14);

    code_label = lv_label_create(scr);
    lv_obj_set_style_text_color(code_label, lv_color_hex(0x888888), LV_PART_MAIN);
    lv_obj_align(code_label, LV_ALIGN_TOP_MID, 0, 10);

    show_next(NULL);
    lv_timer_create(show_next, 2000, NULL);
}

void setup(void)
{
    Serial.begin(115200);

    tft.begin();
    tft.setRotation(1);

    lv_init();
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, SCREEN_W * 10);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res  = SCREEN_W;
    disp_drv.ver_res  = SCREEN_H;
    disp_drv.flush_cb = disp_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    Serial.printf("map-n-flag: %u countries\n", (unsigned)mnf_count());

    build_ui();
}

void loop(void)
{
    lv_timer_handler();
    delay(5);
}
