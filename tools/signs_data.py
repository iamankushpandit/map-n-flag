"""
The American Sign Language (ASL) fingerspelling alphabet.

One entry per letter: (letter, moves). `moves` is True for the two letters
that are traced in the air rather than held -- J (the I hand, hooked
downward) and Z (the index finger drawing a Z). Their source drawings already
carry the motion as an arrow, so the flag is for callers that want to say so
in words, not something the image is missing.

ARTWORK SOURCE
--------------
WPClipart's "American ABCs" sign language set, edited by Paul Sherman
(11/11/2013), as published on Wikimedia Commons:

    https://commons.wikimedia.org/wiki/File:Sign_language_A.svg  ...  _Z.svg

Every file is marked public domain on Commons ("released into the public
domain by its author ... applies worldwide"), and each SVG carries a CC0 1.0
dedication in its own RDF metadata. Nothing about it restricts this library or
anything built with it. tools/fetch_sources.py downloads them into
vendor/asl-wpclipart/ and checks each one's size against Commons.
"""

SIGNS = [(chr(c), chr(c) in "JZ") for c in range(ord("A"), ord("Z") + 1)]

# Commons file title for a letter. The download URL is resolved through the
# Commons API at fetch time rather than written down here, because the upload
# path contains a hash that is Commons' business, not ours.
def commons_title(letter: str) -> str:
    return f"File:Sign_language_{letter.upper()}.svg"
