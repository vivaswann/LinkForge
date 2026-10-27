"""QR Code generation utility for LinkForge short links."""
from __future__ import annotations

import io
import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_png(short_url: str) -> bytes:
    """Generate a crisp PNG QR code encoding the provided short URL.
    
    The QR code encodes the actual short URL, not the destination URL directly.
    """
    qr = qrcode.QRCode(
        version=None,  # automatic size
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(short_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0b0d14", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
