"""Lectura del Excel y claves de cada disco, sin pasar por HTTP."""
import tempfile
from pathlib import Path

from openpyxl import Workbook

from app.security import check_password, hash_password
from app.services.catalog import detect, disc_key, read_discs


def sheet(*rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    f = Path(tempfile.mkstemp(suffix=".xlsx")[1])
    wb.save(f)
    return f


def plan_of(f, saved=None):
    p = detect(f, saved or {})
    return p["header_row"], {c["index"]: c["field"] for c in p["columns"]}


def test_english_header_and_numeric_barcode():
    f = sheet(["Artist", "Title", "Label", "", "Barcode", "Medium", "Description", "Genre"],
              ["MURPHY, Peter", "Deep", "Beggars", None, 801061019716, "Vinyl", "LP", "Indie"],
              [None] * 8)
    row, mapping = plan_of(f)
    assert row == 1
    assert mapping == {0: "artist", 1: "title", 2: "label", 3: "ignore", 4: "barcode", 5: "media", 6: "description", 7: "genre"}
    assert read_discs(f, row, mapping) == (
        [(2, "MURPHY, Peter", "Deep", "Beggars", "Vinyl", "LP", "Indie", "", "", "801061019716", "",
          "v2:murphy peter|deep|vinyl|beggars|lp|801061019716")], [])


def test_spanish_header_below_logo_with_own_column():
    f = sheet(["CHOPP & ROCK RECORDS"], [],
              ["Artista", "Título / Álbum", "Origen", "Insert", "Precio (ARS)"],
              ["ABBA", "The Singles (2xLP Gatefold)", "Reino Unido", "Sí", 75000.0])
    row, mapping = plan_of(f)
    assert row == 3 and mapping == {0: "artist", 1: "title", 2: "origin", 3: "custom", 4: "price"}
    assert read_discs(f, row, mapping) == (
        [(4, "ABBA", "The Singles (2xLP Gatefold)", "", "", "", "", "75000", "Reino Unido", "", '{"Insert": "Sí"}',
          "v2:abba|the singles 2xlp gatefold||||")],
        [{"key": "insert", "name": "Insert"}])
    assert read_discs(f, row, {**mapping, 3: "extra"})[0][0][5] == "Insert: Sí"  # o a la descripción
    assert plan_of(f, {"insert": "ignore"})[1][3] == "ignore"  # lo guardado le gana a la adivinanza


def test_editions_have_different_keys():
    a = {"artist": "MADONNA", "title": "Confessions II", "media": "CD", "label": "Warner",
         "description": "CD in stickered case", "barcode": "93624821304"}
    assert disc_key(a) != disc_key({**a, "description": "CD + poster", "barcode": "93624822356"})
    assert disc_key(a) == disc_key({**a, "artist": "Madonna "})  # mayúsculas y espacios no cuentan


def test_passwords():
    stored = hash_password("secreto")
    assert check_password("secreto", stored) and not check_password("otro", stored)
