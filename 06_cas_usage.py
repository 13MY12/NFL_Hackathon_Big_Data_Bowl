"""
06_cas_usage.py — Fiche de tendance d'un WR star, lisible par un non-spécialiste.

Entrées : outputs/score_wr_type_route.csv, outputs/routes.csv, outputs/trajectoires.csv,
          outputs/plays_stakes.csv, data/players.csv
Sorties : outputs/stars_qualifiees.csv, outputs/fiche_<nom>.png (star principale),
          outputs/fiche_<nom>.png (bonus : la star la plus imprévisible quand l'enjeu monte)

Star principale : la star significative au score le plus élevé, sinon la star qualifiée au score
le plus élevé, sinon le WR qualifié au score le plus élevé.
"""

import os
import re
import sys
import unicodedata
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

RACINE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(RACINE, "data")
OUT = os.path.join(RACINE, "outputs")
CLES = ["gameId", "playId", "nflId"]
plt.rcParams.update({"font.size": 11})

STARS = ["Cooper Kupp", "Davante Adams", "Tyreek Hill", "Justin Jefferson", "Ja'Marr Chase",
         "Deebo Samuel", "CeeDee Lamb", "Stefon Diggs", "DK Metcalf", "Mike Evans", "Chris Godwin",
         "Keenan Allen", "A.J. Brown", "Diontae Johnson", "Tyler Lockett", "Terry McLaurin",
         "DJ Moore", "Amari Cooper", "Mike Williams", "Hunter Renfrow", "Marquise Brown",
         "Jaylen Waddle", "Adam Thielen", "Brandin Cooks"]
TYPES = ["Flat/Screen", "Retour", "Slant", "Out", "In/Dig", "Go", "Post", "Corner", "Autre"]
COULEURS = {"Flat/Screen": "#8c564b", "Retour": "#ff7f0e", "Slant": "#e377c2", "Out": "#1f77b4",
            "In/Dig": "#9467bd", "Go": "#d62728", "Post": "#bcbd22", "Corner": "#17becf",
            "Autre": "#7f7f7f"}
CONSEILS = {"Out": "jouer son côté extérieur", "Corner": "jouer son côté extérieur",
            "Slant": "fermer l'intérieur", "In/Dig": "fermer l'intérieur", "Post": "fermer l'intérieur",
            "Go": "garder un safety profond sur lui",
            "Retour": "ne pas reculer, attaquer le point de retour",
            "Flat/Screen": "un linebacker prêt sur le flat",
            "Autre": "rester en couverture de zone"}


def verifier_entrees():
    # Arrête le script si une entrée manque
    for chemin in [os.path.join(OUT, f) for f in ["score_wr_type_route.csv", "routes.csv",
                                                   "trajectoires.csv", "plays_stakes.csv"]] \
                  + [os.path.join(DATA, "players.csv")]:
        if not os.path.exists(chemin):
            print(f"Fichier manquant : {chemin}")
            sys.exit(1)


def normaliser(nom):
    # "D.J. Moore" et "DJ Moore" -> "djmoore" (pour retrouver les stars dans displayName)
    nom = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", nom.lower())


def nom_fichier(nom):
    # displayName -> nom de fichier sans accents ni espaces
    nom = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_]", "", nom.replace(" ", "_"))


def dessiner_terrain(ax):
    # Fond de terrain : terrain.py s'il existe, sinon un fond simple dessiné ici
    if os.path.exists(os.path.join(RACINE, "terrain.py")):
        try:
            import terrain
            terrain.dessiner_terrain(ax)
            return
        except Exception as e:
            print(f"  terrain.py inutilisable ({e}), fond par défaut")
    ax.set_facecolor("#3d8b3d")
    for yd in range(-10, 60, 5):
        ax.axhline(yd, color="white", lw=1.2 if yd % 10 == 0 else 0.5, alpha=0.7, zorder=0)
        if yd > 0 and yd % 10 == 0:
            ax.text(0.02, yd, f"+{yd}", transform=ax.get_yaxis_transform(), color="white",
                    fontsize=10, va="bottom", fontweight="bold")
    ax.axhline(0, color="#4da6ff", lw=3, zorder=1)                     # ligne de mêlée
    ax.axvline(0, color="white", lw=0.8, ls=":", zorder=1)             # position du ballon
    ax.plot(0, 0, marker="o", ms=9, color="#8b4513", mec="white", zorder=5)


def table_stars(scores, players, routes):
    # Retrouve les stars dans players.csv et garde les WR qualifiés
    cle = players[players["officialPosition"] == "WR"].copy()
    cle["cle"] = cle["displayName"].map(normaliser)
    trouves = cle[cle["cle"].isin([normaliser(s) for s in STARS])]
    introuvables = [s for s in STARS if normaliser(s) not in set(trouves["cle"])]
    print(f"Stars trouvées dans players.csv : {len(trouves)}/{len(STARS)}"
          + (f" | introuvables : {', '.join(introuvables)}" if introuvables else ""))

    equipe = routes.groupby("nflId")["possessionTeam"].agg(lambda s: s.mode().iloc[0])
    st = scores[scores["nflId"].isin(trouves["nflId"])].copy()
    st["equipe"] = st["nflId"].map(equipe)
    st = st.sort_values("score_lisibilite_enjeu", ascending=False)
    non_qualifiees = sorted(set(trouves["displayName"]) - set(st["displayName"]))
    print(f"Stars qualifiées (>= 30 routes en enjeu élevé et >= 30 en normal) : {len(st)}")
    if non_qualifiees:
        print(f"  non qualifiées : {', '.join(non_qualifiees)}")
    vue = pd.DataFrame({
        "nom": st["displayName"], "équipe": st["equipe"], "n normal": st["n_normal"],
        "n élevé": st["n_eleve"], "habitude": st["habitude"],
        "taux normal": (st["taux_habitude_normal"] * 100).round(1),
        "taux élevé": (st["taux_habitude_eleve"] * 100).round(1),
        "score (pts)": (st["score_lisibilite_enjeu"] * 100).round(1),
        "p-value": st["p_value"].round(3), "q-value": st["q_value"].round(3),
        "significatif (p<0,05)": st["significatif"],
    })
    print(vue.to_string(index=False))
    chemin = os.path.join(OUT, "stars_qualifiees.csv")
    vue.to_csv(chemin, index=False)
    print(f"Écrit : {chemin} ({len(vue)} lignes)")
    return st


def phrase_conseil(nom, parts_normal, parts_eleve):
    # « Quand l'enjeu monte, <nom> court un <type> dans X % des cas (contre Y %) → <conseil> »
    dominant = parts_eleve.idxmax()
    x, y = parts_eleve[dominant], parts_normal.get(dominant, 0.0)
    return (f"Quand l'enjeu monte, {nom} court un {dominant} dans {x:.0f} % des cas "
            f"(contre {y:.0f} % habituellement) → {CONSEILS[dominant]}")


def fiche(wr, routes, traj, motif):
    # Fiche : en-tête, barres normal/élevé, deux cartes de routes, phrase de conseil
    nom = wr["displayName"]
    r = routes[routes["nflId"] == wr["nflId"]]
    parts = {e: r[r["enjeu_eleve"] == e]["type_route"].value_counts(normalize=True)
                 .reindex(TYPES, fill_value=0) * 100 for e in (False, True)}
    conseil = phrase_conseil(nom, parts[False], parts[True])

    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.1, 1, 1], left=0.075, right=0.98, top=0.83,
                          bottom=0.17, wspace=0.18)

    # (a) En-tête
    etoile = " ★" if wr["significatif"] else ""
    statut = (f"significatif, p = {wr['p_value']:.3f}" if wr["significatif"]
              else f"tendance non significative, p = {wr['p_value']:.2f}")
    fig.suptitle(f"{nom}{etoile} ({wr['equipe']}) : fiche de tendance quand l'enjeu monte", fontsize=18,
                 fontweight="bold", y=0.97)
    fig.text(0.5, 0.895,
             f"{len(r)} routes ({wr['n_normal']} en enjeu normal, {wr['n_eleve']} en enjeu élevé) | "
             f"habitude : {wr['habitude']} | score de lisibilité {wr['score_lisibilite_enjeu'] * 100:+.1f} pts "
             f"({statut}) | choix : {motif}", ha="center", fontsize=12)

    # (b) Barres côte à côte
    ax = fig.add_subplot(gs[0])
    pos = np.arange(len(TYPES))
    ax.barh(pos + 0.2, parts[False], height=0.4, color="#9e9e9e", label="Enjeu normal")
    ax.barh(pos - 0.2, parts[True], height=0.4, color="#d62728", label="Enjeu élevé")
    for p, v1, v2 in zip(pos, parts[False], parts[True]):
        ax.text(v1 + 0.5, p + 0.2, f"{v1:.0f} %", va="center", fontsize=10)
        ax.text(v2 + 0.5, p - 0.2, f"{v2:.0f} %", va="center", fontsize=10, color="#d62728")
    ax.set_yticks(pos); ax.set_yticklabels(TYPES); ax.invert_yaxis()
    ax.set_xlabel("Part de ses routes (%)")
    ax.set_title("Quelles routes court-il ?", fontsize=13)
    ax.set_xlim(0, max(parts[False].max(), parts[True].max()) * 1.25)
    ax.legend(loc="lower right"); ax.grid(axis="x", alpha=0.3)

    # (c) Cartes de routes (30 routes max par panneau, graine 42)
    tirages = {}
    for e in (False, True):
        sel = r[r["enjeu_eleve"] == e]
        tirages[e] = sel.sample(min(30, len(sel)), random_state=42)
    t_sel = traj.merge(pd.concat(tirages.values())[CLES + ["type_route", "enjeu_eleve"]], on=CLES)
    xmin, xmax = min(-3, t_sel["ecart_ballon"].min() - 2), t_sel["ecart_ballon"].max() + 2
    ymin, ymax = -5, max(20, t_sel["profondeur"].max() + 3)
    for i, e in enumerate((False, True)):
        ax = fig.add_subplot(gs[i + 1])
        dessiner_terrain(ax)
        for (_, _, _), tt in t_sel[t_sel["enjeu_eleve"] == e].groupby(CLES):
            tt = tt.sort_values("frame_rel")
            col = COULEURS[tt["type_route"].iloc[0]]
            ax.plot(tt["ecart_ballon"], tt["profondeur"], color=col, lw=2, alpha=0.9, zorder=3)
            ax.plot(tt["ecart_ballon"].iloc[-1], tt["profondeur"].iloc[-1], "o", color=col,
                    mec="white", ms=6, zorder=4)
        ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)
        ax.set_xlabel("Distance au ballon (yards) — ligne de touche à droite")
        if i == 0:
            ax.set_ylabel("Yards au-delà de la ligne de mêlée")
        n = len(tirages[e])
        ax.set_title(f"Enjeu {'élevé' if e else 'normal'} : {n} routes tirées au hasard", fontsize=13,
                     color="#d62728" if e else "black")
    poignees = [Line2D([0], [0], color=COULEURS[t], lw=3, label=t) for t in TYPES]
    poignees.append(Line2D([0], [0], color="#4da6ff", lw=3, label="Ligne de mêlée"))
    fig.legend(handles=poignees, loc="lower center", ncol=10, fontsize=10,
               bbox_to_anchor=(0.62, 0.075), frameon=False)

    # (d) Phrase de conseil
    fig.text(0.5, 0.025, conseil, ha="center", fontsize=15, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.5", fc="#fff3cd", ec="#d4a017"))

    chemin = os.path.join(OUT, f"fiche_{nom_fichier(nom)}.png")
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    print(f"Conseil : {conseil}")
    print(f"Écrit : {chemin}")


def main():
    # Console Windows (cp1252) : on force l'UTF-8 pour afficher « → » et « ★ »
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier_entrees()
    scores = pd.read_csv(os.path.join(OUT, "score_wr_type_route.csv"))
    players = pd.read_csv(os.path.join(DATA, "players.csv"))
    enjeu = pd.read_csv(os.path.join(OUT, "plays_stakes.csv"),
                        usecols=["gameId", "playId", "enjeu_eleve", "possessionTeam"])
    routes = pd.read_csv(os.path.join(OUT, "routes.csv")).merge(enjeu, on=["gameId", "playId"])
    routes["enjeu_eleve"] = routes["enjeu_eleve"].astype(bool)
    traj = pd.read_csv(os.path.join(OUT, "trajectoires.csv"))
    equipe = routes.groupby("nflId")["possessionTeam"].agg(lambda s: s.mode().iloc[0])

    st = table_stars(scores, players, routes)

    # Choix de la star principale
    if st["significatif"].any():
        star, motif = st[st["significatif"]].iloc[0], "star significative au score le plus haut"
    elif len(st):
        star, motif = st.iloc[0], "star qualifiée au score le plus haut (aucune significative)"
    else:
        star = scores.sort_values("score_lisibilite_enjeu", ascending=False).iloc[0].copy()
        star["equipe"] = equipe.get(star["nflId"], "?")
        motif = "aucune star qualifiée : WR qualifié au score le plus haut"
    print(f"\nStar principale : {star['displayName']} ({motif})")
    fiche(star, routes, traj, motif)

    # Bonus : la star la plus imprévisible quand l'enjeu monte
    if len(st) >= 2:
        bas = st.iloc[-1]
        print(f"\nBonus, star la plus imprévisible : {bas['displayName']}")
        fiche(bas, routes, traj, "star qualifiée au score le plus bas")


if __name__ == "__main__":
    main()
