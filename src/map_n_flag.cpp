/*
 * map-n-flag lookup and pixel access. Hand-written; not generated.
 */
#include "map_n_flag.h"
#include <string.h>
#include <ctype.h>

extern const mnf_country_t mnf_country_table[];
extern const uint16_t mnf_country_count;

extern const mnf_state_t mnf_state_table[];
extern const uint16_t mnf_state_count_val;

extern const mnf_card_t mnf_card_table[];
extern const uint16_t mnf_card_count_val;
extern const mnf_img_t *const mnf_card_back_img;

extern const mnf_sign_t mnf_sign_table[];
extern const uint16_t mnf_sign_count_val;

/* ------------------------------------------------------------------------
 * Country lookup
 * ---------------------------------------------------------------------- */

size_t mnf_count(void)
{
    return (size_t)mnf_country_count;
}

const mnf_country_t *mnf_at(size_t index)
{
    if (index >= (size_t)mnf_country_count) return NULL;
    return &mnf_country_table[index];
}

const mnf_country_t *mnf_find(const char *iso2)
{
    if (iso2 == NULL || iso2[0] == '\0' || iso2[1] == '\0') return NULL;

    /* The table is sorted by upper-case ISO code. */
    const char key0 = (char)toupper((unsigned char)iso2[0]);
    const char key1 = (char)toupper((unsigned char)iso2[1]);

    int lo = 0;
    int hi = (int)mnf_country_count - 1;
    while (lo <= hi) {
        const int mid = lo + (hi - lo) / 2;
        const char *c = mnf_country_table[mid].iso2;
        int cmp = (c[0] - key0);
        if (cmp == 0) cmp = (c[1] - key1);

        if (cmp == 0) return &mnf_country_table[mid];
        if (cmp < 0)  lo = mid + 1;
        else          hi = mid - 1;
    }
    return NULL;
}

const mnf_img_t *mnf_flag(const char *iso2)
{
    const mnf_country_t *c = mnf_find(iso2);
    return c ? c->flag : NULL;
}

const mnf_img_t *mnf_map(const char *iso2)
{
    const mnf_country_t *c = mnf_find(iso2);
    return c ? c->map : NULL;
}

const char *mnf_name(const char *iso2)
{
    const mnf_country_t *c = mnf_find(iso2);
    return c ? c->name : NULL;
}

bool mnf_has_both(const char *iso2)
{
    const mnf_country_t *c = mnf_find(iso2);
    return c != NULL && c->flag != NULL && c->map != NULL;
}

/* ------------------------------------------------------------------------
 * US state lookup
 * ---------------------------------------------------------------------- */

size_t mnf_state_count(void)
{
    return (size_t)mnf_state_count_val;
}

const mnf_state_t *mnf_state_at(size_t index)
{
    if (index >= (size_t)mnf_state_count_val) return NULL;
    return &mnf_state_table[index];
}

const mnf_state_t *mnf_state_find(const char *st)
{
    if (st == NULL || st[0] == '\0' || st[1] == '\0') return NULL;

    const char key0 = (char)toupper((unsigned char)st[0]);
    const char key1 = (char)toupper((unsigned char)st[1]);

    int lo = 0;
    int hi = (int)mnf_state_count_val - 1;
    while (lo <= hi) {
        const int mid = lo + (hi - lo) / 2;
        const char *c = mnf_state_table[mid].iso2;
        int cmp = (c[0] - key0);
        if (cmp == 0) cmp = (c[1] - key1);

        if (cmp == 0) return &mnf_state_table[mid];
        if (cmp < 0)  lo = mid + 1;
        else          hi = mid - 1;
    }
    return NULL;
}

const mnf_img_t *mnf_state_flag(const char *st)
{
    const mnf_state_t *s = mnf_state_find(st);
    return s ? s->flag : NULL;
}

const mnf_img_t *mnf_state_map(const char *st)
{
    const mnf_state_t *s = mnf_state_find(st);
    return s ? s->map : NULL;
}

const char *mnf_state_name(const char *st)
{
    const mnf_state_t *s = mnf_state_find(st);
    return s ? s->name : NULL;
}

bool mnf_state_has_both(const char *st)
{
    const mnf_state_t *s = mnf_state_find(st);
    return s != NULL && s->flag != NULL && s->map != NULL;
}

/* ------------------------------------------------------------------------
 * Playing card lookup
 * ---------------------------------------------------------------------- */

size_t mnf_card_count(void)
{
    return (size_t)mnf_card_count_val;
}

const mnf_card_t *mnf_card_at(size_t index)
{
    if (index >= (size_t)mnf_card_count_val) return NULL;
    return &mnf_card_table[index];
}

const mnf_card_t *mnf_card_find(const char *code)
{
    if (code == NULL || code[0] == '\0' || code[1] == '\0') return NULL;

    /* Codes are upper-case ASCII, so the table's plain char ordering is the
     * same ordering the generator sorted by. */
    const char key0 = (char)toupper((unsigned char)code[0]);
    const char key1 = (char)toupper((unsigned char)code[1]);

    int lo = 0;
    int hi = (int)mnf_card_count_val - 1;
    while (lo <= hi) {
        const int mid = lo + (hi - lo) / 2;
        const char *c = mnf_card_table[mid].code;
        int cmp = (c[0] - key0);
        if (cmp == 0) cmp = (c[1] - key1);

        if (cmp == 0) return &mnf_card_table[mid];
        if (cmp < 0)  lo = mid + 1;
        else          hi = mid - 1;
    }
    return NULL;
}

const mnf_card_t *mnf_card_by(uint8_t rank, uint8_t suit)
{
    /* 52 entries and the table is sorted by code, not by value, so a linear
     * scan is both the simplest and the smallest thing that works. */
    for (uint16_t i = 0; i < mnf_card_count_val; i++) {
        if (mnf_card_table[i].rank == rank && mnf_card_table[i].suit == suit) {
            return &mnf_card_table[i];
        }
    }
    return NULL;
}

const mnf_img_t *mnf_card(const char *code)
{
    const mnf_card_t *c = mnf_card_find(code);
    return c ? c->img : NULL;
}

const char *mnf_card_name(const char *code)
{
    const mnf_card_t *c = mnf_card_find(code);
    return c ? c->name : NULL;
}

const mnf_img_t *mnf_card_back(void)
{
    return mnf_card_back_img;
}

bool mnf_card_is_red(const mnf_card_t *card)
{
    if (card == NULL) return false;
    if (card->suit == MNF_SUIT_HEARTS || card->suit == MNF_SUIT_DIAMONDS) return true;
    /* Jokers carry no suit; the red one is "ZR". */
    return card->suit == MNF_SUIT_NONE && card->code != NULL && card->code[1] == 'R';
}

/* ------------------------------------------------------------------------
 * ASL fingerspelling
 * ---------------------------------------------------------------------- */

size_t mnf_sign_count(void)
{
    return (size_t)mnf_sign_count_val;
}

const mnf_sign_t *mnf_sign_at(size_t index)
{
    if (index >= (size_t)mnf_sign_count_val) return NULL;
    return &mnf_sign_table[index];
}

const mnf_sign_t *mnf_sign_find(char letter)
{
    /* The table is A to Z with no gaps, so a letter is its own index. */
    const int up = toupper((unsigned char)letter);
    if (up < 'A' || up > 'Z') return NULL;
    return mnf_sign_at((size_t)(up - 'A'));
}

const mnf_img_t *mnf_sign(char letter)
{
    const mnf_sign_t *s = mnf_sign_find(letter);
    return s ? s->img : NULL;
}

/* ------------------------------------------------------------------------
 * Pixel access
 * ---------------------------------------------------------------------- */

uint16_t mnf_rgb565(uint8_t r, uint8_t g, uint8_t b)
{
    return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

uint8_t mnf_index_at(const mnf_img_t *img, uint16_t x, uint16_t y)
{
    if (img == NULL || x >= img->w || y >= img->h) return 0;

    const uint8_t *row = img->data + MNF_PALETTE_BYTES + (size_t)MNF_STRIDE(img->w) * y;
    const uint8_t byte = row[x >> 1];
    /* Leftmost pixel of each pair is the high nibble. */
    return (x & 1) ? (byte & 0x0F) : (byte >> 4);
}

uint32_t mnf_palette_argb(const mnf_img_t *img, uint8_t index)
{
    if (img == NULL || index >= MNF_PALETTE_ENTRIES) return 0;

    const uint8_t *e = img->data + (size_t)index * 4;   /* B, G, R, A */
    return ((uint32_t)e[3] << 24) | ((uint32_t)e[2] << 16) |
           ((uint32_t)e[1] << 8)  | (uint32_t)e[0];
}

uint32_t mnf_pixel_argb(const mnf_img_t *img, uint16_t x, uint16_t y)
{
    if (img == NULL || x >= img->w || y >= img->h) return 0;
    return mnf_palette_argb(img, mnf_index_at(img, x, y));
}

/* Split RGB565 back into 8-bit components for blending. */
static void unpack565(uint16_t c, uint8_t *r, uint8_t *g, uint8_t *b)
{
    *r = (uint8_t)(((c >> 11) & 0x1F) * 255 / 31);
    *g = (uint8_t)(((c >> 5) & 0x3F) * 255 / 63);
    *b = (uint8_t)((c & 0x1F) * 255 / 31);
}

void mnf_row_rgb565(const mnf_img_t *img, uint16_t y, uint16_t *out, uint16_t bg565)
{
    if (img == NULL || out == NULL || y >= img->h) return;

    uint8_t br, bg, bb;
    unpack565(bg565, &br, &bg, &bb);

    /* Composite the 16 palette entries once per row rather than per pixel. */
    uint16_t lut[MNF_PALETTE_ENTRIES];
    for (uint8_t i = 0; i < MNF_PALETTE_ENTRIES; i++) {
        const uint8_t *e = img->data + (size_t)i * 4;   /* B, G, R, A */
        const uint16_t a = e[3];
        if (a == 255) {
            lut[i] = mnf_rgb565(e[2], e[1], e[0]);
        } else if (a == 0) {
            lut[i] = bg565;
        } else {
            const uint16_t ia = 255 - a;
            lut[i] = mnf_rgb565((uint8_t)((e[2] * a + br * ia) / 255),
                                (uint8_t)((e[1] * a + bg * ia) / 255),
                                (uint8_t)((e[0] * a + bb * ia) / 255));
        }
    }

    const uint8_t *row = img->data + MNF_PALETTE_BYTES + (size_t)MNF_STRIDE(img->w) * y;
    for (uint16_t x = 0; x < img->w; x++) {
        const uint8_t byte = row[x >> 1];
        out[x] = lut[(x & 1) ? (byte & 0x0F) : (byte >> 4)];
    }
}

void mnf_row_rgb565_tint(const mnf_img_t *img, uint16_t y, uint16_t *out,
                         uint16_t bg565, uint16_t fg565)
{
    if (img == NULL || out == NULL || y >= img->h) return;

    uint8_t br, bg, bb, fr, fg, fb;
    unpack565(bg565, &br, &bg, &bb);
    unpack565(fg565, &fr, &fg, &fb);

    /* Alpha comes from the palette entry; colour is ignored. For map
     * silhouettes the palette is an alpha ramp, so index == alpha level. */
    uint16_t lut[MNF_PALETTE_ENTRIES];
    for (uint8_t i = 0; i < MNF_PALETTE_ENTRIES; i++) {
        const uint16_t a = img->data[(size_t)i * 4 + 3];
        const uint16_t ia = 255 - a;
        lut[i] = mnf_rgb565((uint8_t)((fr * a + br * ia) / 255),
                            (uint8_t)((fg * a + bg * ia) / 255),
                            (uint8_t)((fb * a + bb * ia) / 255));
    }

    const uint8_t *row = img->data + MNF_PALETTE_BYTES + (size_t)MNF_STRIDE(img->w) * y;
    for (uint16_t x = 0; x < img->w; x++) {
        const uint8_t byte = row[x >> 1];
        out[x] = lut[(x & 1) ? (byte & 0x0F) : (byte >> 4)];
    }
}
