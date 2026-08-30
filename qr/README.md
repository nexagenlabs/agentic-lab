# QR codes for the printed URLs

13 codes, error correction level H, quiet zone 4 modules.

**Minimum printed size 2.0 cm square.** Below that, phone cameras struggle at arm's length, which is the distance somebody holds a book at.

Only the thirteen addresses the book prints get a code. There is deliberately no ch01 or ch02: those chapters ship no code and the book prints no address for them.

Every code below was decoded with zxing-cpp, which shares no code with the encoder, and compared against the URL it was generated from.

| File | Encodes | Decoded back to | Version | Modules | Match |
|---|---|---|---|---|---|
| `qr/hub.png` | https://lab.nexagenlabs.com/ | https://lab.nexagenlabs.com/ | 4 | 33 x 33 | yes |
| `qr/ch03.png` | https://lab.nexagenlabs.com/ch03 | https://lab.nexagenlabs.com/ch03 | 4 | 33 x 33 | yes |
| `qr/ch04.png` | https://lab.nexagenlabs.com/ch04 | https://lab.nexagenlabs.com/ch04 | 4 | 33 x 33 | yes |
| `qr/ch05.png` | https://lab.nexagenlabs.com/ch05 | https://lab.nexagenlabs.com/ch05 | 4 | 33 x 33 | yes |
| `qr/ch06.png` | https://lab.nexagenlabs.com/ch06 | https://lab.nexagenlabs.com/ch06 | 4 | 33 x 33 | yes |
| `qr/ch07.png` | https://lab.nexagenlabs.com/ch07 | https://lab.nexagenlabs.com/ch07 | 4 | 33 x 33 | yes |
| `qr/ch08.png` | https://lab.nexagenlabs.com/ch08 | https://lab.nexagenlabs.com/ch08 | 4 | 33 x 33 | yes |
| `qr/ch09.png` | https://lab.nexagenlabs.com/ch09 | https://lab.nexagenlabs.com/ch09 | 4 | 33 x 33 | yes |
| `qr/ch10.png` | https://lab.nexagenlabs.com/ch10 | https://lab.nexagenlabs.com/ch10 | 4 | 33 x 33 | yes |
| `qr/ch11.png` | https://lab.nexagenlabs.com/ch11 | https://lab.nexagenlabs.com/ch11 | 4 | 33 x 33 | yes |
| `qr/ch12.png` | https://lab.nexagenlabs.com/ch12 | https://lab.nexagenlabs.com/ch12 | 4 | 33 x 33 | yes |
| `qr/references.png` | https://lab.nexagenlabs.com/references | https://lab.nexagenlabs.com/references | 5 | 37 x 37 | yes |
| `qr/setup.png` | https://lab.nexagenlabs.com/setup | https://lab.nexagenlabs.com/setup | 4 | 33 x 33 | yes |


## Regenerating

```
python tools/verify_printed_urls.py    # must exit 0
python tools/generate_qr_codes.py
```

The generator refuses to encode any URL the verification tool did not mark OK
in its most recent run. A QR code encoding a dead URL is worse than no QR code,
because a reader can judge a printed address before typing it and cannot judge
a black square before scanning it.

## For the typesetter

- **Do not crop the white margin.** It is a four-module quiet zone and it is
  part of the symbol, not padding. Many scanners will not see a code without
  it.
- **Do not print below 2 cm square.** Phone cameras struggle at arm's length
  below that, which is how far away a book is held.
- **Do not recolour, screen back, or place on a texture or photograph.** Level
  H tolerates damage, not low contrast. Black on white, full strength.
- **Nothing may overlap the three corner squares.** A logo or a caption over
  one is fatal at any size, because a scanner has to find the symbol before
  error correction does anything at all.
- Files are named for their chapter, so `ch07.png` belongs beside the Chapter 7
  address and nowhere else. There is no `ch01.png` or `ch02.png`, because those
  chapters ship no code and the book prints no address for them.

## How much damage these actually survive

Level H is specified to restore about thirty per cent of a symbol's codewords.
That is not a number a typesetter can act on, so these codes were damaged on
purpose to find one that is:

| Damage | Result |
|---|---|
| Contiguous blot over 20% of the symbol, clear of the corners | decodes |
| Contiguous blot over 23% | fails |
| Any blot across a corner square or the alignment pattern | fails at any size |
| 10% of modules randomised, scattered | fails |

Scattered speckle is much worse than one blot of the same area, because a
single wrong module ruins the entire eight-module codeword it sits in. Treat
the margin as insurance against a fold or a coffee ring in one place, not
against a bad print run everywhere.
