"""
02_extract_routes.py — Une ligne de mesures par route de WR, du snap au lancer.

Entrées : data/players.csv, data/pffScoutingData.csv, data/plays.csv, data/tracking/*.csv
Sorties :
  - mode normal (122 matchs) : outputs/routes.csv, outputs/trajectoires.csv
  - mode `--echantillon` (10 matchs) : outputs/grille_routes.png + contrôles console
    (arrêt avec code 1 si "Autre" > 20 %)

Méthode (fichier de tracking traité un par un) :
  1. snap = 1re frame ball_snap (sinon autoevent_ballsnap) ; lancer = 1re frame pass_forward
     (sinon autoevent_passforward). Actions sans snap ou sans lancer exclues.
  2. Normalisation : si playDirection == "left", x = 120 - x et y = 53,3 - y (attaque vers la droite).
  3. Ligne de mêlée = x du ballon au snap ; côté du WR = signe de (y du WR - y du ballon) au snap.
  4. Mesures : prof_max, prof_au_lancer, recul, lateral (positif vers l'extérieur), vitesse_au_lancer.
  5. type_route par les règles V3 (ordre fixe), vs_marqueur par rapport à yardsToGo.
"""

import os
import sys
import glob
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RACINE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(RACINE, "data")
TRACK = os.path.join(DATA, "tracking")
OUT = os.path.join(RACINE, "outputs")
CLES = ["gameId", "playId", "nflId"]

TYPES = ["Flat/Screen", "Retour", "Slant", "Out", "In/Dig", "Go", "Post", "Corner", "Autre"]
REF_TYPES = {"Out": 25.2, "Autre": 14.5, "Go": 12.6, "In/Dig": 11.4, "Slant": 10.7,
             "Retour": 10.1, "Flat/Screen": 8.2, "Corner": 5.0, "Post": 2.3}
REF_VS = {"avant": 34.8, "au_marqueur": 26.7, "au_dela": 38.6}
EVTS = ["ball_snap", "autoevent_ballsnap", "pass_forward", "autoevent_passforward"]


def verifier_entrees():
    # Arrête le script si une entrée manque
    for f in ["players.csv", "pffScoutingData.csv", "plays.csv"]:
        if not os.path.exists(os.path.join(DATA, f)):
            print(f"Fichier manquant : {os.path.join(DATA, f)}")
            sys.exit(1)
    if not glob.glob(os.path.join(TRACK, "tracking_*.csv")):
        print(f"Fichiers de tracking manquants dans : {TRACK}")
        sys.exit(1)


def charger_cles_wr():
    # (gameId, playId, nflId) des WR en "Pass Route", avec leur position d'alignement PFF
    players = pd.read_csv(os.path.join(DATA, "players.csv"))
    pff = pd.read_csv(os.path.join(DATA, "pffScoutingData.csv"))
    wr = set(players.loc[players["officialPosition"] == "WR", "nflId"])
    cles = pff[(pff["pff_role"] == "Pass Route") & pff["nflId"].isin(wr)]
    cles = cles[CLES + ["pff_positionLinedUp"]].drop_duplicates(CLES).copy()
    cles["nflId"] = cles["nflId"].astype(float)  # le nflId du tracking est float (NaN pour le ballon)
    return cles


def frames_evenements(t):
    # Frame de snap et de lancer par action, avec les motifs d'exclusion
    ev = t[t["event"].notna() & (t["event"] != "None")]
    piv = ev.groupby(["gameId", "playId", "event"])["frameId"].min().unstack()
    k = t[["gameId", "playId"]].drop_duplicates().set_index(["gameId", "playId"]).join(piv)
    for c in EVTS:
        if c not in k.columns:
            k[c] = np.nan
    k["snap"] = k["ball_snap"].fillna(k["autoevent_ballsnap"])        # manuel prioritaire
    k["lancer"] = k["pass_forward"].fillna(k["autoevent_passforward"])
    k["snap_auto"] = k["ball_snap"].isna() & k["autoevent_ballsnap"].notna()
    k["lancer_auto"] = k["pass_forward"].isna() & k["autoevent_passforward"].notna()
    k["sans_snap"] = k["snap"].isna()
    k["sans_lancer"] = k["lancer"].isna()
    k["lancer_avant_snap"] = k["snap"].notna() & k["lancer"].notna() & (k["lancer"] <= k["snap"])
    k["ok"] = ~(k["sans_snap"] | k["sans_lancer"] | k["lancer_avant_snap"])
    return k.reset_index()


def traiter_fichier(chemin, cles):
    # Lit un match, renvoie (routes, trajectoires, table des actions, nb routes incomplètes)
    t = pd.read_csv(chemin, usecols=["gameId", "playId", "nflId", "frameId", "team",
                                     "playDirection", "x", "y", "s", "event"])
    k = frames_evenements(t)
    ok = k.loc[k["ok"], ["gameId", "playId", "snap", "lancer"]]

    # Normalisation : l'attaque va toujours vers la droite
    gauche = t["playDirection"] == "left"
    t.loc[gauche, "x"] = 120 - t.loc[gauche, "x"]
    t.loc[gauche, "y"] = 53.3 - t.loc[gauche, "y"]

    # Fenêtre snap -> lancer
    t = t.merge(ok, on=["gameId", "playId"])
    t = t[(t["frameId"] >= t["snap"]) & (t["frameId"] <= t["lancer"])]

    # Ballon au snap : ligne de mêlée (x) et repère des côtés (y)
    ballon = t[(t["team"] == "football") & (t["frameId"] == t["snap"])]
    ballon = ballon[["gameId", "playId", "x", "y"]].drop_duplicates(["gameId", "playId"])
    ballon = ballon.rename(columns={"x": "los", "y": "y_ballon"})

    w = t.merge(cles, on=CLES).merge(ballon, on=["gameId", "playId"])
    w = w.sort_values(CLES + ["frameId"])
    w["profondeur"] = w["x"] - w["los"]

    a = w.groupby(CLES).agg(
        f0=("frameId", "first"), f1=("frameId", "last"),
        snap=("snap", "first"), lancer=("lancer", "first"),
        prof_max=("profondeur", "max"), prof_au_lancer=("profondeur", "last"),
        prof_au_snap=("profondeur", "first"),
        x0=("x", "first"), y0=("y", "first"), y1=("y", "last"),
        vitesse_au_lancer=("s", "last"), y_ballon=("y_ballon", "first"),
        pff_positionLinedUp=("pff_positionLinedUp", "first"),
    ).reset_index()

    # Le WR doit être présent au snap ET au lancer
    complet = (a["f0"] == a["snap"]) & (a["f1"] == a["lancer"])
    n_incomplet = int((~complet).sum())
    a = a[complet].copy()

    a["cote"] = np.where(a["y0"] >= a["y_ballon"], 1, -1)       # +1 : WR au-dessus du ballon
    a["lateral"] = a["cote"] * (a["y1"] - a["y0"])              # > 0 : vers l'extérieur
    a["recul"] = a["prof_max"] - a["prof_au_lancer"]

    # Trajectoires relatives au snap, extérieur toujours positif
    tr = w.merge(a[CLES + ["cote", "x0", "y0"]], on=CLES)
    traj = pd.DataFrame({
        "gameId": tr["gameId"], "playId": tr["playId"], "nflId": tr["nflId"],
        "frame_rel": (tr["frameId"] - tr["snap"]).astype(int),
        "avance": (tr["x"] - tr["x0"]).round(1),
        "lateral": (tr["cote"] * (tr["y"] - tr["y0"])).round(1),
        "profondeur": tr["profondeur"].round(1),
        "ecart_ballon": (tr["cote"] * (tr["y"] - tr["y_ballon"])).round(1),
    })
    colonnes = CLES + ["prof_au_snap", "prof_max", "prof_au_lancer", "recul", "lateral",
                       "vitesse_au_lancer", "pff_positionLinedUp"]
    return a[colonnes], traj, k, n_incomplet


def classer_routes(r):
    # Règles V3, appliquées dans l'ordre (la première vraie l'emporte) ; NaN -> comparaison fausse
    pm, lat, rec, v = r["prof_max"], r["lateral"], r["recul"], r["vitesse_au_lancer"]
    conditions = [
        pm < 3,                                                     # Flat/Screen
        ((rec >= 1) | (v < 2.5)) & (pm >= 3) & (pm <= 18),          # Retour
        (pm >= 3) & (pm <= 8) & (lat <= -2),                        # Slant
        (pm >= 3) & (pm <= 15) & (lat >= 2),                        # Out
        (pm >= 8) & (pm <= 18) & (lat <= -2),                       # In/Dig
        (pm >= 10) & (lat.abs() < 2),                               # Go
        (pm >= 15) & (lat <= -2),                                   # Post
        (pm >= 15) & (lat >= 2),                                    # Corner
    ]
    return np.select(conditions, TYPES[:-1], default="Autre")


def classer_marqueur(prof, ytg):
    # Position au lancer par rapport au marqueur de premier essai (bornes incluses)
    return np.where(prof < ytg - 2, "avant", np.where(prof <= ytg + 2, "au_marqueur", "au_dela"))


def afficher_repartition(serie, ordre, ref, titre):
    # Part de chaque modalité et écart à la référence de l'exploration
    print(f"\n{titre} ({len(serie)} routes) :")
    parts = serie.value_counts(normalize=True) * 100
    for m in ordre:
        p = parts.get(m, 0.0)
        e = p - ref[m]
        alerte = "  ÉCART > 2 pts" if abs(e) > 2 else ""
        print(f"  {m:<12} {p:5.1f} %  (réf. {ref[m]:4.1f} %, écart {e:+.1f}){alerte}")
    return parts


def dessiner_grille(routes, traj, chemin):
    # 9 vignettes (une par type), 5 routes tirées avec la graine 42, extérieur à droite
    fig, axes = plt.subplots(3, 3, figsize=(13, 13), sharex=True, sharey=True)
    total = len(routes)
    for ax, typ in zip(axes.ravel(), TYPES):
        sel = routes[routes["type_route"] == typ]
        n = len(sel)
        tirage = sel.sample(min(5, n), random_state=42) if n else sel
        for _, r in tirage.iterrows():
            tt = traj[(traj["gameId"] == r["gameId"]) & (traj["playId"] == r["playId"])
                      & (traj["nflId"] == r["nflId"])]
            ax.plot(tt["lateral"], tt["profondeur"], lw=2)
            ax.plot(tt["lateral"].iloc[-1], tt["profondeur"].iloc[-1], "ko", ms=4)
        ax.axhline(0, color="royalblue", lw=1, ls="--")
        ax.axvline(0, color="grey", lw=0.5)
        txt = f"{typ} : {n} routes ({100 * n / total:.1f} %)"
        if 0 < n < 5:
            txt += f", {n} dessinées"
        ax.set_title(txt, fontsize=11)
        if n == 0:
            ax.text(0.5, 0.5, "aucune route", transform=ax.transAxes, ha="center")
        ax.grid(alpha=0.3)
    for ax in axes[-1]:
        ax.set_xlabel("Déplacement latéral (yards, extérieur à droite)", fontsize=10)
    for ax in axes[:, 0]:
        ax.set_ylabel("Profondeur / ligne de mêlée (yards)", fontsize=10)
    fig.suptitle("Contrôle visuel des règles de routes V3 (10 matchs, 5 routes par type)\n"
                 "trait bleu = ligne de mêlée, point noir = position au lancer", fontsize=13)
    fig.tight_layout()
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    print(f"Écrit : {chemin}")


def main():
    debut = time.time()
    verifier_entrees()
    os.makedirs(OUT, exist_ok=True)
    echantillon = "--echantillon" in sys.argv

    cles = charger_cles_wr()
    plays = pd.read_csv(os.path.join(DATA, "plays.csv"), usecols=["gameId", "playId", "yardsToGo"])
    fichiers = sorted(glob.glob(os.path.join(TRACK, "tracking_*.csv")))
    if echantillon:
        fichiers = fichiers[:10]
    print(f"Mode {'ÉCHANTILLON (10 matchs)' if echantillon else 'COMPLET'} : {len(fichiers)} fichiers")

    routes, trajs, actions, n_incomplet = [], [], [], 0
    for i, f in enumerate(fichiers, 1):
        r, tr, k, n_inc = traiter_fichier(f, cles)
        routes.append(r); trajs.append(tr); actions.append(k); n_incomplet += n_inc
        if i % 20 == 0:
            print(f"  {i}/{len(fichiers)} fichiers traités ({time.time() - debut:.0f} s)")
    R = pd.concat(routes, ignore_index=True)
    T = pd.concat(trajs, ignore_index=True)
    K = pd.concat(actions, ignore_index=True)

    # Exclusions (chaque motif compté indépendamment)
    print(f"\nActions dans le tracking : {len(K)}")
    print(f"  exclues sans snap          : {int(K['sans_snap'].sum())}")
    print(f"  exclues sans lancer        : {int(K['sans_lancer'].sum())}")
    print(f"  exclues lancer <= snap     : {int(K['lancer_avant_snap'].sum())}")
    print(f"Routes exclues (WR absent au snap ou au lancer) : {n_incomplet}")

    R["type_route"] = classer_routes(R)
    R = R.merge(plays, on=["gameId", "playId"], how="left")
    R["vs_marqueur"] = classer_marqueur(R["prof_au_lancer"], R["yardsToGo"])
    R = R.drop(columns="yardsToGo")
    R["nflId"] = R["nflId"].astype(int)
    T["nflId"] = T["nflId"].astype(int)

    parts = afficher_repartition(R["type_route"], TYPES, REF_TYPES, "Répartition des type_route")
    afficher_repartition(R["vs_marqueur"], list(REF_VS), REF_VS, "Répartition de vs_marqueur")

    if echantillon:
        ok = K[K["ok"]]
        duree = ok["lancer"] - ok["snap"]
        print(f"\nActions avec snap auto : {int(K['snap_auto'].sum())} (réf. 0) | "
              f"avec lancer auto : {int(K['lancer_auto'].sum())} (réf. 8)")
        print(f"Frames snap -> lancer : médiane {duree.median():.0f}, min {duree.min():.0f}, "
              f"max {duree.max():.0f} (réf. 26 / 13 / 98)")
        print(f"Profondeur médiane du WR au snap : {R['prof_au_snap'].median():.2f} yd (réf. -0,85)")
        dessiner_grille(R, T, os.path.join(OUT, "grille_routes.png"))
        autre = parts.get("Autre", 0.0)
        if autre > 20.0:
            print(f"\n'Autre' = {autre:.1f} % > 20 %")
            print("STOP : valider les règles type_route avant les 122 matchs")
            sys.exit(1)
        print(f"\n'Autre' = {autre:.1f} % <= 20 % : règles V3 validées, lancer sans --echantillon.")
        print(f"Durée : {time.time() - debut:.1f} s")
        return

    chemin_r = os.path.join(OUT, "routes.csv")
    R.to_csv(chemin_r, index=False)
    print(f"\nÉcrit : {chemin_r} ({len(R)} lignes)")
    chemin_t = os.path.join(OUT, "trajectoires.csv")
    T.to_csv(chemin_t, index=False)
    taille = os.path.getsize(chemin_t) / 1e6
    n_traj = T.groupby(CLES).ngroups
    print(f"Écrit : {chemin_t} ({len(T)} lignes, {n_traj} routes, {taille:.1f} Mo)")
    print(f"Routes : {len(R)} (attendu 19 356 à 21 392) | WR distincts : {R['nflId'].nunique()} "
          f"(attendu 199 à 219)")
    print(f"Durée totale : {time.time() - debut:.1f} s (attendu < 120 s)")


if __name__ == "__main__":
    main()
