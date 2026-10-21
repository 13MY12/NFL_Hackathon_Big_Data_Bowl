"""
08_final.py — Visualisations finales (outputs/final/), combinaison IMPOSÉE :
indice V1, seuil >= 4, choix = intention (Jeu rapide / Vers la touche / Vers le milieu / Vertical,
"Autre" exclu), minimum 20 routes en enjeu élevé ET 20 en normal, 1 000 permutations.

Entrées : outputs/routes.csv, outputs/plays_stakes.csv, outputs/trajectoires.csv,
          outputs/sensibilite/robustesse.csv, outputs/sensibilite/sensibilite.png, data/players.csv
Sorties : outputs/final/score_wr_intention.csv, fiche_Mike_Evans.png, fiche_Brandon_Aiyuk.png,
          classement.png, effet_equipe.png, nuage.png, sensibilite.png

Usage : `py 08_final.py` (tout) ou `py 08_final.py fiche_evans classement` (étapes choisies).
Étapes : fiche_evans, fiche_aiyuk, classement, equipe, nuage, sensibilite.

Vocabulaire : ★ seulement si q < 0,10 (Benjamini-Hochberg) ; ◆ « tendance » si p < 0,05 non corrigé.
"""

import os
import re
import sys
import shutil
import unicodedata
import importlib.util
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.stats import binom

RACINE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(RACINE, "data")
OUT = os.path.join(RACINE, "outputs")
FINAL = os.path.join(OUT, "final")
CLES = ["gameId", "playId", "nflId"]

# --- Combinaison imposée -------------------------------------------------------------------
SEUIL = 4
MINIMUM = 20
INTENTION = {"Flat/Screen": "Jeu rapide", "Slant": "Jeu rapide", "Retour": "Jeu rapide",
             "Out": "Vers la touche", "Corner": "Vers la touche",
             "In/Dig": "Vers le milieu", "Post": "Vers le milieu", "Go": "Vertical"}  # Autre exclu
INTENTIONS = ["Jeu rapide", "Vers la touche", "Vers le milieu", "Vertical"]

# --- Charte commune ---------------------------------------------------------------------------
GRIS, ROUGE = "#9e9e9e", "#d62728"            # enjeu normal / enjeu élevé
VIOLET, VERT = "#7b2cbf", "#2a9d8f"           # plus lisible / plus imprévisible
COUL_INT = {"Jeu rapide": "#f4a261", "Vers la touche": "#1f77b4",
            "Vers le milieu": "#9467bd", "Vertical": "#e63946"}
CONSEIL = {"Vers la touche": "jouer son côté extérieur", "Vers le milieu": "fermer l'intérieur",
           "Vertical": "garder un safety profond", "Jeu rapide": "presser à la ligne"}
PIED = "Données NFL Next Gen Stats + PFF, 2021 sem. 1-8 | indice V1, seuil ≥4, 4 intentions"
DPI = 200
plt.rcParams.update({"font.size": 12, "axes.titlesize": 14, "axes.labelsize": 12,
                     "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 12})


def verifier_entrees():
    # Arrête le script si une entrée manque
    requis = [os.path.join(OUT, f) for f in ["routes.csv", "plays_stakes.csv", "trajectoires.csv"]] + \
             [os.path.join(OUT, "sensibilite", f) for f in ["robustesse.csv", "sensibilite.png"]] + \
             [os.path.join(DATA, "players.csv")]
    for chemin in requis:
        if not os.path.exists(chemin):
            print(f"Fichier manquant : {chemin}")
            sys.exit(1)


def charger_module(fichier, alias):
    # Importe 03_habitude.py (nom commençant par un chiffre) pour réutiliser score_habitude
    spec = importlib.util.spec_from_file_location(alias, os.path.join(RACINE, fichier))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pied_de_page(fig):
    # Pied de page commun à toutes les figures
    fig.text(0.5, 0.012, PIED, ha="center", va="bottom", fontsize=12, color="dimgray")


def marque(r):
    # ★ si q < 0,10 ; ◆ si p < 0,05 (tendance, non corrigé) ; rien sinon
    if r["q_value"] < 0.10:
        return " ★"
    return " ◆" if r["p_value"] < 0.05 else ""


def fr(x, d=1, signe=False):
    # Nombre au format français (virgule décimale)
    return (f"{x:+.{d}f}" if signe else f"{x:.{d}f}").replace(".", ",")


def nom_fichier(nom):
    # displayName -> nom de fichier sans accents ni espaces
    nom = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_]", "", nom.replace(" ", "_"))


def sauver(fig, nom):
    # Enregistre en 200 dpi dans outputs/final/
    chemin = os.path.join(FINAL, nom)
    fig.savefig(chemin, dpi=DPI)
    plt.close(fig)
    print(f"Écrit : {chemin}")


# --- Données ----------------------------------------------------------------------------------
def preparer():
    # Routes avec intention + scores de la combinaison imposée
    enjeu = pd.read_csv(os.path.join(OUT, "plays_stakes.csv"),
                        usecols=["gameId", "playId", "indice_enjeu", "possessionTeam"])
    routes = pd.read_csv(os.path.join(OUT, "routes.csv")).merge(enjeu, on=["gameId", "playId"])
    routes["intention"] = routes["type_route"].map(INTENTION)
    routes = routes[routes["intention"].notna()].copy()           # "Autre" exclu
    routes["enjeu_eleve"] = routes["indice_enjeu"] >= SEUIL        # indice V1 (01_build_plays)

    m03 = charger_module("03_habitude.py", "habitude")
    table = routes[["nflId", "gameId", "playId", "intention", "enjeu_eleve"]].rename(
        columns={"intention": "choix"})
    res, _ = m03.score_habitude(table, minimum_force=MINIMUM)
    noms = pd.read_csv(os.path.join(DATA, "players.csv"), usecols=["nflId", "displayName"])
    equipe = routes.groupby("nflId")["possessionTeam"].agg(lambda s: s.mode().iloc[0]).rename("equipe")
    res = res.merge(noms, on="nflId", how="left").merge(equipe, left_on="nflId", right_index=True)
    res = res.sort_values("score_lisibilite_enjeu", ascending=False)
    res.drop(columns="significatif").to_csv(os.path.join(FINAL, "score_wr_intention.csv"), index=False)

    n, n_p = len(res), int((res["p_value"] < 0.05).sum())
    p_binom = binom.sf(n_p - 1, n, 0.05)                          # P(X >= n_p) si aucun effet réel
    print(f"Combinaison imposée : {n} WR qualifiés (20/20), {n_p} à p < 0,05 "
          f"(attendus {0.05 * n:.1f}, test binomial p = {p_binom:.3f}), "
          f"{int((res['q_value'] < 0.10).sum())} à q < 0,10")
    rob = pd.read_csv(os.path.join(OUT, "sensibilite", "robustesse.csv"))
    return routes, res, rob, p_binom


def parts_intention(r):
    # Part (%) de chaque intention en enjeu normal et élevé
    return {e: r[r["enjeu_eleve"] == e]["intention"].value_counts(normalize=True)
                .reindex(INTENTIONS, fill_value=0) * 100 for e in (False, True)}


# --- 1. Fiche joueur --------------------------------------------------------------------------
def terrain(ax):
    # Fond de terrain : gazon, lignes tous les 5 yards, ligne de mêlée, ballon
    ax.set_facecolor("#2e6b30")
    for yd in range(-10, 60, 5):
        ax.axhline(yd, color="white", lw=1.4 if yd % 10 == 0 else 0.6, alpha=0.55, zorder=0)
    ax.axhline(0, color="white", lw=3.5, zorder=1)
    ax.plot(0, 0, marker="o", ms=11, color="#8b4513", mec="white", mew=1.5, zorder=6)


def fiche(nom, routes, res, rob, traj):
    # Fiche de tendance : en-tête, barres des 4 intentions, deux cartes, encadré de conseil
    wr = res[res["displayName"] == nom]
    if wr.empty:
        print(f"{nom} n'est pas qualifié dans la combinaison imposée")
        return
    wr = wr.iloc[0]
    r = routes[routes["nflId"] == wr["nflId"]]
    parts = parts_intention(r)
    ecart = parts[True] - parts[False]
    monte, baisse = ecart.idxmax(), ecart.idxmin()
    rb = rob[rob["nflId"] == wr["nflId"]]
    n_top, n_comb = (int(rb["n_top10_lisibles"].iloc[0]), int(rb["n_combinaisons_qualifie"].iloc[0])) \
        if len(rb) else (0, 0)

    fig = plt.figure(figsize=(20, 11.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1, 1], left=0.055, right=0.985,
                          top=0.80, bottom=0.25, wspace=0.16)

    # En-tête : titre-conclusion + chiffres clés
    fig.suptitle(f"{nom}{marque(wr)} ({wr['equipe']}) : quand l'enjeu monte, « {monte} » passe de "
                 f"{parts[False][monte]:.0f} % à {parts[True][monte]:.0f} % de ses routes",
                 fontsize=21, fontweight="bold", y=0.975)
    tendance = ("◆ tendance, p < 0,05 non corrigé" if wr["p_value"] < 0.05
                else "au-dessus du seuil de tendance de 0,05 sur cette seule combinaison")
    fig.text(0.5, 0.895,
             f"{wr['n_normal']} routes en enjeu normal | {wr['n_eleve']} en enjeu élevé | habitude : "
             f"{wr['habitude']} | score de lisibilité {fr(wr['score_lisibilite_enjeu'] * 100, 1, True)} pts | "
             f"p = {fr(wr['p_value'], 3)} ({tendance})", ha="center", fontsize=14)
    fig.text(0.5, 0.855, f"Dans le top 10 des WR les plus lisibles pour {n_top} des {n_comb} combinaisons "
                         f"testées où il est qualifié (analyse de sensibilité)",
             ha="center", fontsize=14, color=VIOLET, fontweight="bold")

    # Barres côte à côte des 4 intentions
    ax = fig.add_subplot(gs[0])
    x = np.arange(len(INTENTIONS))
    ax.bar(x - 0.2, parts[False], width=0.4, color=GRIS, label="Enjeu normal")
    ax.bar(x + 0.2, parts[True], width=0.4, color=ROUGE, label="Enjeu élevé")
    for xi, v1, v2 in zip(x, parts[False], parts[True]):
        ax.text(xi - 0.2, v1 + 1, f"{v1:.0f} %", ha="center", fontsize=12)
        ax.text(xi + 0.2, v2 + 1, f"{v2:.0f} %", ha="center", fontsize=12, color=ROUGE, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([i.replace("Vers la ", "Vers la\n").replace("Vers le ", "Vers le\n")
                        for i in INTENTIONS])
    for t, i in zip(ax.get_xticklabels(), INTENTIONS):
        t.set_color(COUL_INT[i]); t.set_fontweight("bold")
    ax.set_ylim(0, max(parts[False].max(), parts[True].max()) * 1.22)
    ax.set_ylabel("Part de ses routes (%)")
    ax.set_title("Que fait-il de ses routes ?", fontsize=15)
    ax.legend(loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)

    # Cartes : 30 routes max par niveau d'enjeu, graine 42, colorées par intention
    tir = pd.concat([r[r["enjeu_eleve"] == e].sample(min(30, int((r["enjeu_eleve"] == e).sum())),
                                                     random_state=42) for e in (False, True)])
    t = traj.merge(tir[CLES + ["intention", "enjeu_eleve"]], on=CLES)
    xmin, xmax = min(-3, t["ecart_ballon"].min() - 2), t["ecart_ballon"].max() + 2
    ymin, ymax = -5, max(20, t["profondeur"].max() + 3)
    contour = [pe.withStroke(linewidth=4.5, foreground="white")]
    for i, e in enumerate((False, True)):
        ax = fig.add_subplot(gs[i + 1])
        terrain(ax)
        for _, tt in t[t["enjeu_eleve"] == e].groupby(CLES):
            tt = tt.sort_values("frame_rel")
            c = COUL_INT[tt["intention"].iloc[0]]
            ax.plot(tt["ecart_ballon"], tt["profondeur"], color=c, lw=2.4, zorder=3, path_effects=contour)
            ax.plot(tt["ecart_ballon"].iloc[-1], tt["profondeur"].iloc[-1], "o", color=c, mec="white",
                    mew=1.2, ms=7, zorder=4)
        ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)
        ax.set_xlabel("Distance au ballon (yards), ligne de touche à droite")
        if i == 0:
            ax.set_ylabel("Yards au-delà de la ligne de mêlée")
        n_tir = int((tir["enjeu_eleve"] == e).sum())
        ax.set_title(f"Enjeu {'élevé' if e else 'normal'} : {n_tir} routes tirées au hasard",
                     fontsize=15, color=ROUGE if e else "black", fontweight="bold" if e else "normal")
    poignees = [Line2D([0], [0], color=COUL_INT[i], lw=4, label=i) for i in INTENTIONS] + [
        Line2D([0], [0], color="white", lw=4, label="Ligne de mêlée",
               path_effects=[pe.withStroke(linewidth=8, foreground="#2e6b30")]),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#555555", ms=9, label="Position au lancer")]
    fig.legend(handles=poignees, loc="center", ncol=6, frameon=False, bbox_to_anchor=(0.62, 0.175))

    # Encadré de conseil
    phrase = (f"Quand l'enjeu monte, {nom} remplace « {baisse} » ({parts[False][baisse]:.0f} % → "
              f"{parts[True][baisse]:.0f} %) par « {monte} » ({parts[False][monte]:.0f} % → "
              f"{parts[True][monte]:.0f} %) → {CONSEIL[monte]}")
    fig.text(0.5, 0.085, phrase, ha="center", va="center", fontsize=17, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.6", fc="#fff3cd", ec="#d4a017", lw=1.5))
    pied_de_page(fig)
    print(f"Conseil : {phrase}")
    sauver(fig, f"fiche_{nom_fichier(nom)}.png")


# --- 2. Classement ----------------------------------------------------------------------------
def classement(res, p_binom):
    # Top 10 / flop 10 du score, ◆ si p < 0,05, n routes et habitude affichés
    n, n_p = len(res), int((res["p_value"] < 0.05).sum())
    sel = pd.concat([res.head(10), res.tail(10)]).iloc[::-1]       # le plus lisible en haut
    scores = sel["score_lisibilite_enjeu"] * 100
    fig, ax = plt.subplots(figsize=(17, 12))
    fig.subplots_adjust(left=0.17, right=0.97, top=0.86, bottom=0.1)
    pos = np.arange(len(sel))
    ax.barh(pos, scores, color=[VIOLET if s > 0 else VERT for s in scores], height=0.72)
    ax.set_yticks(pos)
    ax.set_yticklabels([f"{nm}{marque(r)}" for nm, (_, r) in zip(sel["displayName"], sel.iterrows())])
    ax.axvline(0, color="black", lw=1)
    for p, s, (_, r) in zip(pos, scores, sel.iterrows()):
        txt = f" {r['n_normal'] + r['n_eleve']} routes · habitude : {r['habitude']} "
        ax.text(s, p, txt, va="center", ha="left" if s > 0 else "right", fontsize=12)
    lim = scores.abs().max() * 2.15
    ax.set_xlim(-lim, lim)
    ax.set_xlabel("Score de lisibilité : écart à la moyenne de la fidélité à l'habitude (points de %)")
    fig.suptitle(f"Quand l'enjeu monte, {n_p} WR changent nettement de comportement, "
                 f"contre ~{0.05 * n:.0f} attendus par hasard (p ≈ {p_binom:.2f})".replace(".", ","),
                 fontsize=16, fontweight="bold", y=0.965)
    fig.text(0.5, 0.905, f"Top 10 et flop 10 sur {n} WR qualifiés (≥ 20 routes dans chaque niveau d'enjeu) | "
                         f"combinaison retenue parmi 12 testées (voir annexe)", ha="center", fontsize=13)
    ax.legend(handles=[Patch(color=VIOLET, label="Plus lisible quand l'enjeu monte"),
                       Patch(color=VERT, label="Plus imprévisible quand l'enjeu monte"),
                       Line2D([0], [0], color="w", label="◆ tendance : p < 0,05 (non corrigé)"),
                       Line2D([0], [0], color="w", label="★ : q < 0,10 après correction (aucun ici)")],
              loc="lower right", frameon=True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    pied_de_page(fig)
    sauver(fig, "classement.png")


# --- 3. Effet équipe --------------------------------------------------------------------------
def effet_equipe(routes):
    # Part "Vers la touche" en enjeu normal vs élevé : 6 équipes qui changent le plus + ligue
    r = routes.assign(touche=routes["intention"] == "Vers la touche")
    eq = r.groupby(["possessionTeam", "enjeu_eleve"])["touche"].mean().unstack() * 100
    eq.columns = ["normal", "eleve"]
    eq["n_eleve"] = r[r["enjeu_eleve"]].groupby("possessionTeam").size()
    eq["ecart"] = eq["eleve"] - eq["normal"]
    top = eq.reindex(eq["ecart"].abs().sort_values(ascending=False).index).head(6)
    ligue = r.groupby("enjeu_eleve")["touche"].mean() * 100
    top = top.sort_values("ecart")
    lignes = list(top.index) + ["Moyenne ligue"]
    normal = list(top["normal"]) + [ligue[False]]
    eleve = list(top["eleve"]) + [ligue[True]]
    n_el = list(top["n_eleve"]) + [int(r["enjeu_eleve"].sum())]

    meilleur = top["ecart"].abs().idxmax()
    e = top.loc[meilleur]
    verbe = "augmente" if e["ecart"] > 0 else "réduit"
    # Marge d'erreur à 95 % d'un écart de proportions pour l'équipe la plus marquée (honnêteté)
    n_norm_m = int((r["possessionTeam"] == meilleur).sum() - e["n_eleve"])
    pm = (e["normal"] + e["eleve"]) / 200
    marge = 1.96 * np.sqrt(pm * (1 - pm) * (1 / e["n_eleve"] + 1 / n_norm_m)) * 100
    fig, ax = plt.subplots(figsize=(15, 9.5))
    fig.subplots_adjust(left=0.13, right=0.96, top=0.82, bottom=0.14)
    for y, (a, b, n) in enumerate(zip(normal, eleve, n_el)):
        gras = lignes[y] == "Moyenne ligue"
        ax.plot([a, b], [y, y], color="#555555" if gras else "#bbbbbb", lw=3 if gras else 2, zorder=1)
        ax.scatter([a], [y], s=170, color=GRIS, zorder=3, edgecolor="white")
        ax.scatter([b], [y], s=170, color=ROUGE, zorder=3, edgecolor="white")
        gauche, droite = (a, b) if a < b else (b, a)
        ax.text(gauche - 1.2, y, f"{(a if a < b else b):.0f} %", ha="right", va="center", fontsize=12,
                color=GRIS if a < b else ROUGE, fontweight="bold")
        ax.text(droite + 1.2, y, f"{(b if a < b else a):.0f} %  ({b - a:+.0f} pts, {n} routes à enjeu élevé)",
                ha="left", va="center", fontsize=12, color=ROUGE if a < b else GRIS, fontweight="bold")
    ax.axhline(len(lignes) - 1.5, color="black", lw=0.8, ls=":")
    ax.set_yticks(range(len(lignes)))
    ax.set_yticklabels(lignes)
    ax.get_yticklabels()[-1].set_fontweight("bold")
    ax.set_xlim(min(normal + eleve) - 9, max(normal + eleve) + 30)
    ax.set_ylim(-0.7, len(lignes) - 0.4)
    ax.set_xlabel("Part des routes des WR « Vers la touche » (Out + Corner), en %")
    fig.suptitle(f"Quand l'enjeu monte, {meilleur} est l'équipe qui {verbe} le plus ses routes vers la touche "
                 f"({e['normal']:.0f} % → {e['eleve']:.0f} %)", fontsize=17, fontweight="bold", y=0.965)
    fig.text(0.5, 0.905, f"Les 6 équipes dont la part « Vers la touche » change le plus, et la moyenne de la "
                         f"ligue ({ligue[False]:.0f} % → {ligue[True]:.0f} %)", ha="center", fontsize=13)
    fig.text(0.5, 0.868, f"Prudence : pour {meilleur}, la marge d'erreur à 95 % est d'environ ±{marge:.0f} pts ; "
                         f"ces écarts d'équipe restent du même ordre que le hasard", ha="center", fontsize=13,
             color="dimgray", style="italic")
    ax.legend(handles=[Line2D([0], [0], marker="o", color="w", markerfacecolor=GRIS, ms=12, label="Enjeu normal"),
                       Line2D([0], [0], marker="o", color="w", markerfacecolor=ROUGE, ms=12, label="Enjeu élevé")],
              loc="lower right", frameon=True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    pied_de_page(fig)
    sauver(fig, "effet_equipe.png")
    print(eq.sort_values("ecart").round(1).to_string())


# --- 4. Nuage ---------------------------------------------------------------------------------
def nuage(res):
    # Un point par WR : taux d'habitude normal (x) contre élevé (y), zones annotées
    x, y = res["taux_habitude_normal"] * 100, res["taux_habitude_eleve"] * 100
    decal = res["variation"].mean() * 100
    heros = ["Mike Evans", "Brandon Aiyuk", "Emmanuel Sanders", "Marquise Brown"]
    imp = res[(res["p_value"] < 0.05) & (res["score_lisibilite_enjeu"] < 0)].nsmallest(2, "score_lisibilite_enjeu")
    a_nommer = pd.concat([res[res["displayName"].isin(heros)], imp])
    positifs = [h for h in heros if (res.loc[res["displayName"] == h, "score_lisibilite_enjeu"] > 0).any()]

    bas = min(x.min(), y.min()) - 4              # marge sous 0 pour ne pas coller un point à l'axe
    haut = min(100, max(x.max(), y.max()) + 4)
    fig, ax = plt.subplots(figsize=(13, 13))
    fig.subplots_adjust(left=0.1, right=0.96, top=0.85, bottom=0.1)
    xx = np.array([bas, haut])
    ax.fill_between(xx, xx + decal, haut, color=VIOLET, alpha=0.07, zorder=0)
    ax.fill_between(xx, bas, xx + decal, color=VERT, alpha=0.07, zorder=0)
    ax.plot(xx, xx, color="black", lw=1.2, label="Même fidélité dans les deux cas")
    ax.plot(xx, xx + decal, color="black", lw=1.2, ls="--",
            label=f"Tendance moyenne des WR ({fr(decal, 1, True)} pts)")
    normal = ~res["displayName"].isin(a_nommer["displayName"])
    ax.scatter(x[normal], y[normal], s=55, color="#bdbdbd", edgecolor="white", zorder=2)

    # Positions des étiquettes choisies à la main pour éviter tout chevauchement
    decalages = {"Mike Evans": (-15, 22), "Brandon Aiyuk": (18, 12), "Emmanuel Sanders": (18, -4),
                 "Marquise Brown": (18, 10)}
    for _, r in imp.iterrows():
        decalages[r["displayName"]] = (18, 16)
    for _, r in a_nommer.iterrows():
        c = VIOLET if r["score_lisibilite_enjeu"] > 0 else VERT
        px, py = r["taux_habitude_normal"] * 100, r["taux_habitude_eleve"] * 100
        ax.scatter([px], [py], s=150, color=c, edgecolor="black",
                   marker="D" if r["p_value"] < 0.05 else "o", zorder=4)
        dx, dy = decalages.get(r["displayName"], (18, 8))
        ax.annotate(f"{r['displayName']}{marque(r)}", (px, py), xytext=(dx, dy), textcoords="offset points",
                    fontsize=13, fontweight="bold", color=c, ha="left" if dx > 0 else "right",
                    arrowprops=dict(arrowstyle="-", color=c, lw=1), zorder=5,
                    path_effects=[pe.withStroke(linewidth=3, foreground="white")])
    ax.text(bas + 0.03 * (haut - bas), haut - 0.03 * (haut - bas),
            "PLUS LISIBLE quand l'enjeu monte :\nil répète davantage son habitude",
            color=VIOLET, fontsize=14, fontweight="bold", va="top")
    ax.text(haut - 0.03 * (haut - bas), bas + 0.2 * (haut - bas),
            "PLUS IMPRÉVISIBLE quand l'enjeu monte :\nil s'écarte de son habitude",
            color=VERT, fontsize=14, fontweight="bold", ha="right", va="bottom")
    ax.set_xlim(bas, haut); ax.set_ylim(bas, haut); ax.set_aspect("equal")
    graduations = np.arange(0, haut + 1, 10)                      # pas de graduation négative
    ax.set_xticks(graduations); ax.set_yticks(graduations)
    ax.set_xlabel("Part des routes qui suivent son habitude, enjeu normal (%)")
    ax.set_ylabel("Part des routes qui suivent son habitude, enjeu élevé (%)")
    ax.legend(handles=ax.get_legend_handles_labels()[0] + [
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#777777", ms=10, label="tendance (p < 0,05)")],
        loc="upper left", bbox_to_anchor=(0.01, 0.62), frameon=True)
    # Noms de famille, sauf « M. Brown » (plusieurs Brown dans la ligue)
    courts = [("M. Brown" if n == "Marquise Brown" else n.split(" ")[-1]) for n in positifs]
    noms = ", ".join(courts[:-1]) + f" et {courts[-1]}" if len(courts) > 1 else ", ".join(courts)
    fig.suptitle(f"Quand l'enjeu monte, {noms} s'accrochent à leur habitude", fontsize=17,
                 fontweight="bold", y=0.965)
    fig.text(0.5, 0.905, f"Un point par WR ({len(res)} WR qualifiés) : au-dessus de la ligne pointillée, "
                         f"plus fidèle à son habitude que la moyenne", ha="center", fontsize=13)
    fig.text(0.5, 0.878, "Les 4 noms en violet ressortent dans la majorité des 12 combinaisons testées (annexe)",
             ha="center", fontsize=13, color=VIOLET)
    pied_de_page(fig)
    sauver(fig, "nuage.png")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier_entrees()
    os.makedirs(FINAL, exist_ok=True)
    etapes = set(sys.argv[1:]) or {"fiche_evans", "fiche_aiyuk", "classement", "equipe", "nuage", "sensibilite"}
    routes, res, rob, p_binom = preparer()
    if etapes & {"fiche_evans", "fiche_aiyuk"}:
        traj = pd.read_csv(os.path.join(OUT, "trajectoires.csv"))
        if "fiche_evans" in etapes:
            fiche("Mike Evans", routes, res, rob, traj)
        if "fiche_aiyuk" in etapes:
            fiche("Brandon Aiyuk", routes, res, rob, traj)
    if "classement" in etapes:
        classement(res, p_binom)
    if "equipe" in etapes:
        effet_equipe(routes)
    if "nuage" in etapes:
        nuage(res)
    if "sensibilite" in etapes:
        shutil.copy(os.path.join(OUT, "sensibilite", "sensibilite.png"), os.path.join(FINAL, "sensibilite.png"))
        print(f"Copié : {os.path.join(FINAL, 'sensibilite.png')}")


if __name__ == "__main__":
    main()
