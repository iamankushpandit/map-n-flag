/*
 * map-n-flag -- optional LVGL adapter.
 *
 * Include this ONLY if your project uses LVGL. The core map_n_flag.h has no
 * LVGL dependency, so projects that draw straight to a TFT (TFT_eSPI,
 * LovyanGFX, ...) never pull LVGL in.
 *
 * The image bytes are already exactly what LVGL expects for a 4-bit indexed
 * image, so this adapter only fills in a descriptor struct -- it copies no
 * pixel data and allocates nothing.
 *
 * Usage (the slot must outlive the widget, so make it static):
 *
 *     #include "map_n_flag_lvgl.h"
 *
 *     static mnf_lv_dsc_t flag_slot;
 *     lv_img_set_src(img, mnf_lv_bind(&flag_slot, mnf_flag("FR")));
 *
 * Works on LVGL v8 and v9; the descriptor struct differs between them and
 * that difference is handled below.
 *
 * NOTE: indexed images cannot be scaled at runtime on LVGL v8 -- the decoder
 * streams them from flash line by line, and that draw path ignores zoom and
 * angle. lv_img_set_zoom() will silently do nothing. Regenerate at a larger
 * FLAG_W/FLAG_H instead. See README.md.
 */
#ifndef MAP_N_FLAG_LVGL_H
#define MAP_N_FLAG_LVGL_H

#include "map_n_flag.h"
#include "lvgl.h"

#ifdef __cplusplus
extern "C" {
#endif

#if defined(LVGL_VERSION_MAJOR) && LVGL_VERSION_MAJOR >= 9
typedef lv_image_dsc_t mnf_lv_dsc_t;
#else
typedef lv_img_dsc_t mnf_lv_dsc_t;
#endif

/**
 * Point an LVGL descriptor at a map-n-flag image.
 *
 * @param slot  caller-owned descriptor; must stay alive while LVGL uses it
 * @param img   result of mnf_flag() / mnf_map(), may be NULL
 * @return      slot, or NULL if either argument was NULL
 */
static inline const mnf_lv_dsc_t *mnf_lv_bind(mnf_lv_dsc_t *slot, const mnf_img_t *img)
{
    if (slot == NULL || img == NULL) return NULL;

#if defined(LVGL_VERSION_MAJOR) && LVGL_VERSION_MAJOR >= 9
    slot->header.magic      = LV_IMAGE_HEADER_MAGIC;
    slot->header.cf         = LV_COLOR_FORMAT_I4;
    slot->header.flags      = 0;
    slot->header.w          = img->w;
    slot->header.h          = img->h;
    /* stride is the pixel row length and EXCLUDES the palette. */
    slot->header.stride     = MNF_STRIDE(img->w);
    slot->header.reserved_2 = 0;
    slot->data_size         = MNF_DATA_SIZE(img->w, img->h);
    slot->data              = img->data;
    slot->reserved          = NULL;
#else
    slot->header.cf          = LV_IMG_CF_INDEXED_4BIT;
    slot->header.always_zero = 0;
    slot->header.reserved    = 0;
    slot->header.w           = img->w;
    slot->header.h           = img->h;
    slot->data_size          = MNF_DATA_SIZE(img->w, img->h);
    slot->data               = img->data;
#endif

    return slot;
}

#ifdef __cplusplus
}
#endif

#endif /* MAP_N_FLAG_LVGL_H */
