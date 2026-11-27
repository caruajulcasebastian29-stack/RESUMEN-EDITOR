"""Descarga una película de dominio público desde archive.org para las pruebas del banco.

Se usan películas libres de derechos para no subir a GitHub material ajeno. Prueba varias
candidatas y se queda con la primera que tenga un MP4 descargable.
Uso: python pelicula_libre.py DESTINO.mp4
"""
import json
import sys
import urllib.request

CANDIDATAS = ["Charade_1963", "charade_1963", "night_of_the_living_dead", "His_Girl_Friday_1940",
              "TheGeneral1926", "DetourHD"]


def obtener(ident: str) -> str | None:
    with urllib.request.urlopen(f"https://archive.org/metadata/{ident}", timeout=60) as r:
        meta = json.loads(r.read())
    archivos = [f for f in meta.get("files", []) if f.get("name", "").lower().endswith(".mp4")]
    if not archivos:
        return None
    archivos.sort(key=lambda f: int(f.get("size", 0) or 0))
    medio = [f for f in archivos if 50e6 < int(f.get("size", 0) or 0) < 1.5e9] or archivos
    return f"https://archive.org/download/{ident}/{medio[0]['name']}"


def main(destino: str) -> None:
    for ident in CANDIDATAS:
        try:
            url = obtener(ident)
        except Exception as e:
            print("no se pudo", ident, e)
            continue
        if url:
            print("descargando", url)
            urllib.request.urlretrieve(url, destino)
            print("ok", ident)
            return
    sys.exit("ninguna película libre disponible")


if __name__ == "__main__":
    main(sys.argv[1])
