"""
05_viz.py — Graphiques pour un public non spécialiste.

Entrées : outputs/score_wr_type_route.csv, outputs/score_wr_vs_marqueur.csv
Sorties : outputs/nuage_habitude.png, outputs/classement.png,
          outputs/nuage_habitude_vs_marqueur.png, outputs/classement_vs_marqueur.png
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

RACINE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(RACINE, "outputs")
ROUGE, VERT, GRIS = "#d62728", "#2ca02c", "#9e9e9e"
plt.rcParams.update({"font.size": 11})


def charger(fichier):
    # Lit un CSV de scores ; arrêt propre s'il manque
    chemin = os.path.join(OUT, fichier)
    if not os.path.exists(chemin):
        print(f"Fichier manquant : {chemin}")
        sys.exit(1)
    return pd.read_csv(chemin)


def titre_conclusion(df, precision=""):
    # Titre calculé à partir des données (jamais saisi à la main)
    sig = df[df["significatif"]]
    s_plus = int((sig["score_lisibilite_enjeu"] > 0).sum())
    s_moins = int((sig["score_lisibilite_enjeu"] < 0).sum())
    ligne1 = (f"Quand l'enjeu monte{precision} : {s_plus} WR deviennent plus lisibles, "
              f"{s_moins} plus imprévisibles (sur {len(df)} WR qualifiés, p < 0,05)")
    if s_plus + s_moins == 0:
        ligne2 = "Aucun écart individuel n'est significatif : les habitudes de routes tiennent quand l'enjeu monte"
    else:
        # Honnêteté statistique : test non corrigé, environ 5 % de faux positifs attendus
        ligne2 = f"Test non corrigé : environ {0.05 * len(df):.0f} WR passeraient ce seuil par hasard"
    return ligne1 + "\n" + ligne2


def nuage(df, fichier, precision=""):
    # Un point par WR : taux d'habitude en enjeu normal (x) contre enjeu élevé (y)
    fig, ax = plt.subplots(figsize=(10, 9))
    x = df["taux_habitude_normal"] * 100
    y = df["taux_habitude_eleve"] * 100
    couleurs = np.where(~df["significatif"], GRIS,
                        np.where(df["score_lisibilite_enjeu"] > 0, ROUGE, VERT))
    ax.scatter(x, y, c=couleurs, s=55, alpha=0.8, edgecolor="white")
    ax.plot([0, 100], [0, 100], color="black", lw=1)
    decalage = df["variation"].mean() * 100
    ax.plot([0, 100], [decalage, 100 + decalage], color="black", lw=1, ls="--")

    # Noms : WR significatifs, sinon les 3 plus lisibles et les 3 plus imprévisibles
    if df["significatif"].any():
        a_nommer = df[df["significatif"]]
    else:
        print(f"  {fichier} : aucun WR significatif, on nomme les 3 extrêmes de chaque côté")
        tri = df.sort_values("score_lisibilite_enjeu")
        a_nommer = pd.concat([tri.head(3), tri.tail(3)])
    # Décalages alternés pour éviter que les noms proches se chevauchent
    decalages = [(8, 6), (8, -14), (-10, 10), (-10, -16), (8, 16), (-10, -4)]
    a_nommer = a_nommer.sort_values("taux_habitude_eleve")
    for i, (_, r) in enumerate(a_nommer.iterrows()):
        col = ROUGE if r["score_lisibilite_enjeu"] > 0 else VERT
        px, py = r["taux_habitude_normal"] * 100, r["taux_habitude_eleve"] * 100
        ax.scatter([px], [py], c=col, s=80, edgecolor="black", zorder=3)
        dx, dy = decalages[i % len(decalages)]
        ax.annotate(r["displayName"], (px, py), xytext=(dx, dy), textcoords="offset points",
                    fontsize=10, color=col, fontweight="bold", ha="left" if dx > 0 else "right",
                    arrowprops=dict(arrowstyle="-", color=col, lw=0.8))

    bas = max(0, min(x.min(), y.min()) - 5)
    haut = min(100, max(x.max(), y.max()) + 5)
    ax.set_xlim(bas, haut); ax.set_ylim(bas, haut); ax.set_aspect("equal")
    ax.set_xlabel("Part des routes qui suivent son habitude, enjeu normal (%)")
    ax.set_ylabel("Part des routes qui suivent son habitude, enjeu élevé (%)")
    ax.set_title(titre_conclusion(df, precision), fontsize=11.5)
    legende = [
        Line2D([0], [0], color="black", lw=1, label="Même fidélité à l'habitude dans les deux cas"),
        Line2D([0], [0], color="black", lw=1, ls="--", label="Tendance moyenne des WR"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=ROUGE, ms=9, label="Plus lisible (nom en rouge)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=VERT, ms=9, label="Plus imprévisible (nom en vert)"),
    ]
    ax.legend(handles=legende, loc="upper left", fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    chemin = os.path.join(OUT, fichier)
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    print(f"Écrit : {chemin}")


def classement(df, fichier, precision=""):
    # Barres : 10 WR les plus lisibles (rouge) et 10 plus imprévisibles (vert)
    tri = df.sort_values("score_lisibilite_enjeu", ascending=False)
    sel = pd.concat([tri.head(10), tri.tail(10)]).iloc[::-1]   # le plus haut en haut
    scores = sel["score_lisibilite_enjeu"] * 100
    couleurs = [ROUGE if s > 0 else VERT for s in scores]
    noms = [f"{n} ★" if s else n for n, s in zip(sel["displayName"], sel["significatif"])]

    fig, ax = plt.subplots(figsize=(11, 9))
    pos = np.arange(len(sel))
    ax.barh(pos, scores, color=couleurs)
    ax.set_yticks(pos); ax.set_yticklabels(noms, fontsize=10)
    ax.axvline(0, color="black", lw=1)
    for p, s, n, h in zip(pos, scores, sel["n_normal"] + sel["n_eleve"], sel["habitude"]):
        txt = f" {n} routes, habitude : {h} "
        ax.text(s, p, txt, va="center", ha="left" if s > 0 else "right", fontsize=10)
    lim = scores.abs().max() * 1.9
    ax.set_xlim(-lim, lim)
    ax.set_xlabel("Écart à la moyenne de la fidélité à l'habitude quand l'enjeu monte (points de %)")
    n_sig = int(df["significatif"].sum())
    ax.set_title(f"Qui devient lisible quand l'enjeu monte{precision} ? Top 10 et flop 10 sur {len(df)} WR\n"
                 f"{n_sig} WR significatif(s) (★, p < 0,05 non corrigé, ~{0.05 * len(df):.0f} attendus par hasard)",
                 fontsize=12)
    ax.legend(handles=[Patch(color=ROUGE, label="Plus lisible quand l'enjeu monte"),
                       Patch(color=VERT, label="Plus imprévisible quand l'enjeu monte"),
                       Line2D([0], [0], color="w", label="★ = significatif (p < 0,05)")],
              loc="lower right", fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    chemin = os.path.join(OUT, fichier)
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    print(f"Écrit : {chemin}")


def main():
    os.makedirs(OUT, exist_ok=True)
    tr = charger("score_wr_type_route.csv")
    nuage(tr, "nuage_habitude.png")
    classement(tr, "classement.png")

    vs_chemin = os.path.join(OUT, "score_wr_vs_marqueur.csv")
    if os.path.exists(vs_chemin):
        vs = pd.read_csv(vs_chemin)
        nuage(vs, "nuage_habitude_vs_marqueur.png", " (position par rapport au marqueur)")
        classement(vs, "classement_vs_marqueur.png", " (par rapport au marqueur)")


if __name__ == "__main__":
    main()
