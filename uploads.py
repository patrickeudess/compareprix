"""Validation du CONTENU des images téléversées (le nom/l'extension fournis par le client ne comptent pas)."""

MAX_IMAGE_BYTES = 5 * 1024 * 1024

# signature -> (extension, type MIME)
_SIGNATURES = [
    (b'\x89PNG\r\n\x1a\n', 'png'),
    (b'\xff\xd8\xff', 'jpg'),
    (b'GIF87a', 'gif'),
    (b'GIF89a', 'gif'),
]


def detect_image_extension(header):
    """Retourne 'png' | 'jpg' | 'gif' d'après les premiers octets, sinon None."""
    for magic, ext in _SIGNATURES:
        if header.startswith(magic):
            return ext
    return None
