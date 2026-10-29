"""Validación compartida de datos administrativos; los secretos nunca son campos editables."""
import re
from urllib.parse import urlsplit
from common import APIError


def text(value, label, maximum=160, minimum=1):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum or any(c in value for c in '<>\x00'):
        raise APIError(400, label + ' no es válido.')
    return value.strip()


def email(value):
    value = text(value, 'El correo', 254).lower()
    if not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', value):
        raise APIError(400, 'El correo no es válido.')
    return value


def integer(value, label, low=1, high=1000):
    if type(value) is not int or not low <= value <= high:
        raise APIError(400, label + ' debe ser un entero entre ' + str(low) + ' y ' + str(high) + '.')
    return value


def url(value, label, hosts=None):
    value = text(value, label, 1200)
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or any(c in value for c in '\"\'\r\n\t ') or (hosts and parsed.hostname not in hosts):
        raise APIError(400, label + ' debe ser una URL HTTPS válida y permitida.')
    return value


def active(value):
    if type(value) is not bool:
        raise APIError(400, 'El estado activo debe ser verdadero o falso.')
    return int(value)
