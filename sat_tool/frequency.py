"""Frequency formatting and strict entry, stored exclusively as integer Hz."""
from __future__ import annotations
import re
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP

VALID_STYLES=("radio10","radio1","decimal")

def format_frequency(hz,style="radio10"):
    if hz is None:return "—"
    if isinstance(hz,bool) or not isinstance(hz,(int,float)) or not 0<=hz<1_300_000_000:
        raise ValueError("Frequência inválida")
    value=int(round(hz))
    if style not in VALID_STYLES:raise ValueError("Formato inválido")
    if style=="radio10":
        rounded=(value+5)//10
        mhz,remainder=divmod(rounded,100000)
        khz,tens=divmod(remainder,100)
        return f"{mhz}.{khz:03d}.{tens:02d}"
    mhz,remainder=divmod(value,1_000_000)
    khz,rest=divmod(remainder,1000)
    if style=="radio1":
        return f"{mhz}.{khz:03d}.{rest:03d}"
    return f"{mhz},{remainder:06d}"

def parse_mhz_input(text):
    """Canonical decimal MHz (both separators) and *two* grouped radio formats."""
    raw=str(text).strip().replace(" MHz","").replace("MHz","").strip()
    if re.fullmatch(r"\d{1,4}\.\d{3}\.\d{2}",raw):
        mhz,khz,tens=map(int,raw.split("."))
        value=mhz*1_000_000+khz*1_000+tens*10
    elif re.fullmatch(r"\d{1,4}\.\d{3}\.\d{3}",raw):
        mhz,khz,hz=map(int,raw.split("."))
        value=mhz*1_000_000+khz*1_000+hz
    elif re.fullmatch(r"\d{1,4}(?:[.,]\d{1,6})?",raw):
        try:value=int((Decimal(raw.replace(",","."))*1000000).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
        except InvalidOperation:raise ValueError("Frequência inválida")
    else:raise ValueError("Use 426.252.12 ou 426,252120 MHz")
    if not 100000<=value<=1_299_999_999:raise ValueError("Frequência fora do intervalo CAT")
    return value

def frequency_label(hz,style="radio10"):
    return format_frequency(hz,style)+" MHz" if hz is not None else "—"
