"""Elegir y cortar las tomas para cada frase de la narración nueva.

Reglas (de lo aprendido y de lo que Jhon rechazó en el primer montaje):
  - Se usan las tomas reales detectadas en el video de la App 1, nunca trozos partidos al azar.
  - Se descartan las tomas malas del diagnóstico (negro, repetidas) y lo que no es película.
  - Una toma no se repite en todo el video. Si a una frase le falta imagen, se toman tomas vecinas
    sin usar (las más cercanas en el tiempo de la historia), no se recicla la misma.
  - Los cortes caen al final de una palabra, con duraciones que varían alrededor de la mediana de
    las referencias (nada de duraciones idénticas, que se notan mecánicas).
  - De cada toma se usa su parte central, donde suele estar la acción.
"""
from __future__ import annotations

import random
import re

MALOS = {"negro", "toma_repetida"}
NO_PELICULA = {"pantalla_negra", "autopromocion", "tarjeta_texto", "otro"}


def _tiempos_de_palabras(texto: str, dur: float) -> list[float]:
    """Final aproximado de cada palabra dentro del audio de la frase (las comas y puntos pesan más)."""
    palabras = texto.split()
    if not palabras:
        return [dur]
    pesos = [len(p) + 1 + (4 if re.search(r"[.!?…]$", p) else 2 if p.endswith(",") else 0) for p in palabras]
    total = sum(pesos)
    acum, fines = 0.0, []
    for w in pesos:
        acum += w
        fines.append(dur * acum / total)
    return fines


class Elector:
    def __init__(self, tomas: list[dict], vistas: list[dict], diagnostico: dict, manual: dict, semilla: int = 7):
        malos = [(p["inicio"], p["fin"]) for p in diagnostico.get("problemas", []) if p["tipo"] in MALOS]
        tipo = {v["n"]: v["tipo"] for v in vistas}
        ajeno = {v["n"] for v in vistas  # tomas con la mascota u otro elemento de un canal ajeno encima
                 if any(re.search(r"personaje|mascota|avatar|logo|canal", s_["que"], re.I) for s_ in v.get("superpuesto", []))}
        self.tomas = [t for t in tomas
                      if tipo.get(t["n"], "pelicula") not in NO_PELICULA and t["n"] not in ajeno
                      and not any(a <= t["inicio"] + 0.05 and t["fin"] - 0.05 <= b for a, b in malos)
                      and t["fin"] - t["inicio"] >= 0.5]
        self.usadas: set[int] = set()
        med = (manual.get("duracion_toma_mediana") or {}).get("mediana") or 1.5
        tope = (manual.get("duracion_toma_max") or {}).get("mediana") or 2.6
        self.mediana, self.tope = float(med), float(max(tope, med * 1.3))
        self.azar = random.Random(semilla)

    def _suma(self, lista: list[dict]) -> float:
        return sum(min(t["fin"] - t["inicio"], self.tope) for t in lista)

    def _candidatas(self, fuentes: list[tuple[float, float]], necesito: float) -> list[dict]:
        def en_fuente(t):
            return any(t["inicio"] < b and t["fin"] > a for a, b in fuentes)
        propias = [t for t in self.tomas if t["n"] not in self.usadas and en_fuente(t)]
        if self._suma(propias) < necesito:
            centro = sum((a + b) / 2 for a, b in fuentes) / len(fuentes)
            ya = {t["n"] for t in propias}
            libres = sorted((t for t in self.tomas if t["n"] not in self.usadas and t["n"] not in ya),
                            key=lambda t: abs((t["inicio"] + t["fin"]) / 2 - centro))
            for t in libres:  # tomas vecinas sin usar, de la más cercana a la más lejana
                propias.append(t)
                if self._suma(propias) >= necesito:
                    break
        if self._suma(propias) < necesito:
            # ya no quedan tomas sin usar: se permite repetir las del propio tramo (último recurso)
            propias += [t for t in self.tomas if en_fuente(t)]
        return sorted({t["n"]: t for t in propias}.values(), key=lambda t: t["inicio"])

    def elegir(self, fuentes: list[tuple[float, float]], texto: str, dur: float,
               reservar: bool = True) -> list[tuple[float, float]]:
        """reservar=False para el gancho: sus tomas pueden volver a salir cuando la historia llegue ahí."""
        n_ideal = max(1, round(dur / self.mediana))
        cand = self._candidatas(fuentes, dur)
        if not cand:
            a, _ = fuentes[0]
            return [(a, a + dur)]
        if len(cand) > n_ideal:  # se reparten a lo largo del tramo para seguir el orden de la historia
            paso = len(cand) / n_ideal
            cand = [cand[int(i * paso + paso / 2)] for i in range(n_ideal)]
        fines = _tiempos_de_palabras(texto, dur)
        cortes, t_prev = [], 0.0
        for k in range(1, len(cand)):
            objetivo = t_prev + (dur - t_prev) / (len(cand) - k + 1) * self.azar.uniform(0.75, 1.25)
            mejor = min(fines, key=lambda f: abs(f - objetivo))
            if mejor - t_prev < 0.6 or dur - mejor < 0.6:
                mejor = objetivo
            cortes.append(mejor)
            t_prev = mejor
        bordes = [0.0] + cortes + [dur]
        trozos: list[tuple[float, float]] = []
        sobra = 0.0
        for t, (a, b) in zip(cand, zip(bordes, bordes[1:])):
            largo = (b - a) + sobra
            disp = t["fin"] - t["inicio"]
            usar = min(largo, disp)
            sobra = largo - usar  # si la toma es más corta que su espacio, el resto pasa a la siguiente
            ini = t["inicio"] + (disp - usar) / 2
            trozos.append((round(ini, 3), round(ini + usar, 3)))
            if reservar:
                self.usadas.add(t["n"])
        if sobra > 0.05:  # no alcanzó: se estira la última toma hacia donde tenga imagen
            s, e = trozos[-1]
            ultima = cand[len(trozos) - 1]
            if s - sobra >= ultima["inicio"]:
                trozos[-1] = (round(s - sobra, 3), e)
            else:
                trozos[-1] = (s, round(e + sobra, 3))
        return trozos
