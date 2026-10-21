"""
01_build_plays.py — Indice d'enjeu par action (uniquement des infos d'avant le snap).

Entrées : data/plays.csv, data/games.csv, data/players.csv, data/pffScoutingData.csv
Sortie  : outputs/plays_stakes.csv (une ligne par action)

Indice d'enjeu :
  +1 si 3e tentative, +2 si 4e ; +1 si yardsToGo >= 7 ; +1 si 4e quart-temps (ou prolongation) ;
  +2 si |écart de score| <= 8 ; +1 si <= 2:00 au 2e/4e quart-temps (ou prolongation) ;
  +1 si zone rouge (yards_to_goal <= 20).
Le seuil "enjeu élevé" est choisi parmi >=3, >=4, >=5 : part la plus proche de 35 %
avec au moins 80 WR qualifiés (>= 30 routes en enjeu élevé et >= 30 en normal).
"""

import os
import sys
import numpy as np
import pandas as pd

RACINE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(RACINE, "data")
OUT = os.path.join(RACINE, "outputs")
ENTREES = ["plays.csv", "games.csv", "players.csv", "pffScoutingData.csv"]

# Faits mesurés pendant l'exploration (références pour les contrôles console)
REF_DISTRIB = {0: 106, 1: 1045, 2: 1572, 3: 3298, 4: 1867, 5: 566, 6: 83, 7: 19, 8: 1}
REF_SEUILS = {3: (68.1, 87), 4: (29.1, 83), 5: (7.7, 5)}
MIN_ROUTES = 30


def verifier_entrees():
    # Arrête le script proprement si un fichier d'entrée manque
    for f in ENTREES:
        chemin = os.path.join(DATA, f)
        if not os.path.exists(chemin):
            print(f"Fichier manquant : {chemin}")
            sys.exit(1)


def horloge_en_secondes(gc):
    # Convertit "MM:SS" en secondes restantes dans le quart-temps (repris de explore.py)
    try:
        m, s = str(gc).split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return np.nan


def construire_enjeu(plays, games):
    # Calcule écart de score, yards_to_goal, secondes restantes et indice d'enjeu
    p = plays.merge(games[["gameId", "homeTeamAbbr"]], on="gameId", how="left")
    domicile = p["possessionTeam"] == p["homeTeamAbbr"]
    diff = p["preSnapHomeScore"] - p["preSnapVisitorScore"]
    p["ecart_score"] = np.where(domicile, diff, -diff)  # positif = l'attaque mène
    p["sec_restantes"] = p["gameClock"].map(horloge_en_secondes)

    vide = p["yardlineSide"].isna()
    p["yards_to_goal"] = np.where(
        vide, 50,
        np.where(p["yardlineSide"] == p["possessionTeam"], 100 - p["yardlineNumber"], p["yardlineNumber"]),
    )
    print(f"Actions avec yardlineSide vide (yards_to_goal = 50) : {vide.sum()} (référence 125)")

    # Une condition sur une valeur manquante rapporte 0 point (comparaison fausse)
    q = p["quarter"]
    p["indice_enjeu"] = (
        (p["down"] == 3).astype(int) * 1
        + (p["down"] == 4).astype(int) * 2
        + (p["yardsToGo"] >= 7).astype(int) * 1
        + (q >= 4).astype(int) * 1
        + (p["ecart_score"].abs() <= 8).astype(int) * 2
        + ((p["sec_restantes"] <= 120) & q.isin([2, 4, 5])).astype(int) * 1
        + (p["yards_to_goal"] <= 20).astype(int) * 1
    )
    return p


def compter_qualifies(p, plays_lances, pff, players, seuil):
    # Compte les WR avec >= 30 routes en enjeu élevé ET >= 30 en enjeu normal
    wr = set(players.loc[players["officialPosition"] == "WR", "nflId"])
    r = pff[(pff["pff_role"] == "Pass Route") & pff["nflId"].isin(wr)][["gameId", "playId", "nflId"]]
    r = r.drop_duplicates().merge(plays_lances[["gameId", "playId", "indice_enjeu"]], on=["gameId", "playId"])
    eleve = r["indice_enjeu"] >= seuil
    n_hi = r[eleve].groupby("nflId").size()
    n_lo = r[~eleve].groupby("nflId").size()
    j = pd.concat([n_hi.rename("hi"), n_lo.rename("lo")], axis=1).fillna(0)
    return int(((j["hi"] >= MIN_ROUTES) & (j["lo"] >= MIN_ROUTES)).sum())


def main():
    verifier_entrees()
    os.makedirs(OUT, exist_ok=True)
    plays = pd.read_csv(os.path.join(DATA, "plays.csv"))
    games = pd.read_csv(os.path.join(DATA, "games.csv"))
    players = pd.read_csv(os.path.join(DATA, "players.csv"))
    pff = pd.read_csv(os.path.join(DATA, "pffScoutingData.csv"))

    p = construire_enjeu(plays, games)

    # Contrôle : répartition de l'indice sur les 8 557 actions
    print("\nRépartition de l'indice d'enjeu (toutes actions) :")
    dist = p["indice_enjeu"].value_counts().sort_index()
    for v, n in dist.items():
        ref = REF_DISTRIB.get(int(v), 0)
        print(f"  indice {v} : {n:>5}  (référence {ref:>5}, écart {n - ref:+d})")

    # Choix du seuil sur les actions avec lancer (hors sacks S et scrambles R)
    lances = p[p["passResult"].isin(["C", "I", "IN"])]
    print(f"\nActions avec lancer : {len(lances)} (référence 7 565)")
    print("Seuil | part enjeu élevé | WR qualifiés 30/30 | référence")
    candidats = []
    for s in [3, 4, 5]:
        part = (lances["indice_enjeu"] >= s).mean() * 100
        nq = compter_qualifies(p, lances, pff, players, s)
        rp, rq = REF_SEUILS[s]
        print(f"  >={s} | {part:5.1f} % | {nq:>3} | ({rp} % / {rq})")
        candidats.append((s, part, nq))

    valides = [c for c in candidats if c[2] >= 80]
    # Plus proche de 35 % ; en cas d'égalité le seuil le plus élevé l'emporte
    seuil, part, nq = sorted(valides, key=lambda c: (abs(c[1] - 35), -c[0]))[0]
    print(f"\nSeuil retenu : indice_enjeu >= {seuil} ({part:.1f} % des actions avec lancer, {nq} WR qualifiés)")

    p["enjeu_eleve"] = p["indice_enjeu"] >= seuil
    cols = ["gameId", "playId", "down", "yardsToGo", "quarter", "sec_restantes", "yards_to_goal",
            "ecart_score", "indice_enjeu", "enjeu_eleve", "possessionTeam", "passResult",
            "offenseFormation", "personnelO"]
    chemin = os.path.join(OUT, "plays_stakes.csv")
    p[cols].to_csv(chemin, index=False)
    print(f"Écrit : {chemin} ({len(p)} lignes)")


if __name__ == "__main__":
    main()
