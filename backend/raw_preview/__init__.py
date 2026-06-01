"""
PhotoFlow AI - RAW Preview Module

Extracts embedded JPEG previews from RAW camera files
(.CR2, .NEF, .ARW, .DNG, .CR3, .ORF, .RAF, .RW2, .PEF, .SRW, etc.)
using rawpy.

The extracted JPEG is saved to cache/raw_previews/ and used as
the working file for thumbnail generation and AI detection —
the original RAW file is never decoded to pixel data.
"""
