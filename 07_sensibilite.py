"""
07_sensibilite.py — Analyse de sensibilité du score de lisibilité quand l'enjeu monte.

Ne relit pas le tracking et n'écrase aucun fichier existant : tout va dans outputs/sensibilite/.
Réutilise construire_enjeu (01_build_plays.py) et score_habitude (03_habitude.py).

Entrées : data/plays.csv, data/games.csv, data/players.csv, outputs/routes.csv
Sorties : outputs/sensibilite/grille.csv, scores_toutes_combinaisons.csv, robustesse.csv,
          recommandation.csv, sensibilite.png

Grille (12 combinaisons) :
  indice  V1 = actuel (écart <= 8 -> +2 à tout moment) ; V2 = écart <= 8 -> +2 seulement si quarter >= 3
  seuil   >= 3, >= 4, >= 5
  choix   intention (Jeu rapide / Vers la touche / Vers le milieu / Vertical, "Autre" exclu), type_route
  minimum 20 routes en enjeu élevé ET 20 en normal pour toutes les combinaisons
"""

import os
import sys
import importlib.util
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RACINE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(RACINE, "data")
OUT = os.path.join(RACINE, "outputs")
SENS = os.path.join(OUT, "sensibilite")

INTENTION = {"Flat/Screen": "Jeu rapide", "Slant": "Jeu rapide", "Retour": "Jeu rapide",
             "Out": "Vers la touche", "Corner": "Vers la touche",
             "In/Dig": "Vers le milieu", "Post": "Vers le milieu", "Go": "Vertical"}  # Autre exclu
INDICES = ["V1", "V2"]
SEUILS = [3, 4, 5]
CHOIX = ["intention", "type_route"]
MINIMUM = 20
TOP = 10


def charger_module(fichier, alias):
    # Importe un script dont le nom commence par un chiffre (01_..., 03_...)
    spec = importlib.util.spec_from_file_location(alias, os.path.join(RACINE, fichier))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verifier_entrees():
    # Arrête le script si une entrée manque
    for chemin in [os.path.join(DATA, f) for f in ["plays.csv", "games.csv", "players.csv"]] \
                  + [os.path.join(OUT, "routes.csv")]:
        if not os.path.exists(chemin):
            print(f"Fichier manquant : {chemin}")
            sys.exit(1)


def indices_enjeu(module_enjeu):
    # Indice V1 (construire_enjeu tel quel) et V2 (bonus score serré seulement à partir du 3e QT)
    plays = pd.read_csv(os.path.join(DATA, "plays.csv"))
    games = pd.read_csv(os.path.join(DATA, "games.csv"))
    p = module_enjeu.construire_enjeu(plays, games)
    serre = p["ecart_score"].abs() <= 8
    p["indice_V1"] = p["indice_enjeu"]
    p["indice_V2"] = (p["indice_enjeu"] - 2 * serre.astype(int)
                      + 2 * (serre & (p["quarter"] >= 3)).astype(int))
    p["avec_lancer"] = p["passResult"].isin(["C", "I", "IN"])
    return p[["gameId", "playId", "indice_V1", "indice_V2", "avec_lancer"]]


def format_top(res, plus_lisibles):
    # "Nom (+15.2), Nom (+13.7), ..." : 3 plus lisibles ou 3 plus imprévisibles
    tri = res.sort_values("score_lisibilite_enjeu", ascending=not plus_lisibles).head(3)
    return ", ".join(f"{n} ({s * 100:+.1f})" for n, s in zip(tri["displayName"], tri["score_lisibilite_enjeu"]))


def noms_top3(chaine):
    # Récupère les 3 noms d'une chaîne produite par format_top
    return {x.rsplit(" (", 1)[0].strip() for x in chaine.split("),") if x.strip()}


def lancer_grille(routes, actions, module_habitude, noms):
    # Calcule les 12 combinaisons ; renvoie (grille, scores de toutes les combinaisons)
    lignes, tous = [], []
    for ind in INDICES:
        for seuil in SEUILS:
            part = (actions[f"indice_{ind}"] >= seuil).mean() * 100
            for choix in CHOIX:
                sub = routes[routes["intention"].notna()] if choix == "intention" else routes
                table = pd.DataFrame({
                    "nflId": sub["nflId"], "gameId": sub["gameId"], "playId": sub["playId"],
                    "choix": sub[choix], "enjeu_eleve": sub[f"indice_{ind}"] >= seuil,
                })
                res, _ = module_habitude.score_habitude(table, minimum_force=MINIMUM)
                res = res.merge(noms, on="nflId", how="left")
                n = len(res)
                lignes.append({
                    "indice": ind, "seuil": seuil, "choix": choix,
                    "pct_actions_eleve": round(part, 1), "n_wr_qualifies": n,
                    "n_p05": int((res["p_value"] < 0.05).sum()),
                    "n_attendus_hasard": round(0.05 * n, 1),
                    "n_q10": int((res["q_value"] < 0.10).sum()),
                    "n_q20": int((res["q_value"] < 0.20).sum()),
                    "top3_lisibles": format_top(res, True),
                    "top3_imprevisibles": format_top(res, False),
                })
                res["indice"], res["seuil"], res["choix"] = ind, seuil, choix
                tous.append(res)
    return pd.DataFrame(lignes), pd.concat(tous, ignore_index=True)


def robustesse(tous, routes, noms):
    # Nombre de combinaisons où chaque WR est dans le top 10 lisibles / imprévisibles
    lis, imp = [], []
    for _, res in tous.groupby(["indice", "seuil", "choix"]):
        lis += list(res.nlargest(TOP, "score_lisibilite_enjeu")["nflId"])
        imp += list(res.nsmallest(TOP, "score_lisibilite_enjeu")["nflId"])
    rob = pd.DataFrame({"n_combinaisons_qualifie": tous.groupby("nflId").size()})
    rob["n_top10_lisibles"] = pd.Series(lis).value_counts()
    rob["n_top10_imprevisibles"] = pd.Series(imp).value_counts()
    rob = rob.fillna(0).astype(int)

    # Part de "Vers la touche" (routes hors "Autre"), combinaison de référence V1 >= 4
    r = routes[routes["intention"].notna()].copy()
    r["eleve"] = r["indice_V1"] >= 4
    r["touche"] = r["intention"] == "Vers la touche"
    parts = r.groupby(["nflId", "eleve"])["touche"].mean().unstack() * 100
    rob["part_touche_normal"] = parts[False].round(1)
    rob["part_touche_eleve"] = parts[True].round(1)
    rob["ecart_touche_pts"] = (rob["part_touche_eleve"] - rob["part_touche_normal"]).round(1)
    rob = rob.reset_index().merge(noms, on="nflId", how="left")
    cols = ["nflId", "displayName", "n_combinaisons_qualifie", "n_top10_lisibles",
            "n_top10_imprevisibles", "part_touche_normal", "part_touche_eleve", "ecart_touche_pts"]
    return rob[cols].sort_values(["n_top10_lisibles", "n_top10_imprevisibles"], ascending=False)


def heatmap(grille, chemin):
    # Une heatmap par choix : lignes = indice, colonnes = seuil, valeur = n p<0,05 - n attendus
    grille = grille.assign(exces=grille["n_p05"] - grille["n_attendus_hasard"])
    m = max(1.0, grille["exces"].abs().max())
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    for ax, choix in zip(axes, CHOIX):
        g = grille[grille["choix"] == choix]
        val = g.pivot(index="indice", columns="seuil", values="exces").loc[INDICES, SEUILS]
        nwr = g.pivot(index="indice", columns="seuil", values="n_wr_qualifies").loc[INDICES, SEUILS]
        np05 = g.pivot(index="indice", columns="seuil", values="n_p05").loc[INDICES, SEUILS]
        part = g.pivot(index="indice", columns="seuil", values="pct_actions_eleve").loc[INDICES, SEUILS]
        im = ax.imshow(val.values, cmap="RdBu_r", vmin=-m, vmax=m, aspect="auto")
        for i in range(len(INDICES)):
            for j in range(len(SEUILS)):
                v = val.values[i, j]
                ax.text(j, i, f"{v:+.1f}\n{nwr.values[i, j]} WR qualifiés\n"
                              f"({np05.values[i, j]} WR à p < 0,05)\n{part.values[i, j]:.0f} % d'actions élevées",
                        ha="center", va="center", fontsize=10.5,
                        color="white" if abs(v) > 0.6 * m else "black")   # lisible sur fond foncé
        ax.set_xticks(range(len(SEUILS)))
        ax.set_xticklabels([f"indice ≥ {s}" for s in SEUILS])
        ax.set_yticks(range(len(INDICES)))
        ax.set_yticklabels(["V1 : score serré\ntout le match", "V2 : score serré\nà partir du 3e QT"])
        ax.set_title(f"Choix : {'intention de route' if choix == 'intention' else 'type de route'}",
                     fontsize=13)
    fig.subplots_adjust(left=0.09, right=0.86, top=0.8, bottom=0.1, wspace=0.3)
    cax = fig.add_axes([0.89, 0.15, 0.015, 0.6])                      # barre de couleur à part
    fig.colorbar(im, cax=cax, label="WR à p < 0,05 moins WR attendus\npar hasard (0,05 × n WR)")
    fig.suptitle("Sensibilité : y a-t-il plus de WR « changeants » quand l'enjeu monte que le hasard n'en produit ?\n"
                 "(minimum 20 routes en enjeu élevé et 20 en normal ; bleu = moins que le hasard, rouge = plus)",
                 fontsize=13)
    fig.savefig(chemin, dpi=150)
    plt.close(fig)
    print(f"Écrit : {chemin}")


def recommandation(grille):
    # Combinaisons plausibles (20-40 % d'actions élevées, >= 70 WR) et stabilité de leurs top 3
    # face aux voisines (même choix ; seuil adjacent ou autre indice). Aucun choix selon n p<0,05.
    cand = grille[(grille["pct_actions_eleve"].between(20, 40)) & (grille["n_wr_qualifies"] >= 70)]
    lignes = []
    print("\n=== Recommandation : combinaisons plausibles (20-40 % d'actions élevées, ≥ 70 WR) ===")
    if cand.empty:
        print("Aucune combinaison ne remplit les deux conditions.")
        return pd.DataFrame()
    for _, c in cand.iterrows():
        voisines = grille[(grille["choix"] == c["choix"]) & (
            ((grille["indice"] == c["indice"]) & ((grille["seuil"] - c["seuil"]).abs() == 1))
            | ((grille["indice"] != c["indice"]) & (grille["seuil"] == c["seuil"])))]
        lis, imp = noms_top3(c["top3_lisibles"]), noms_top3(c["top3_imprevisibles"])
        details, stable = [], True
        for _, v in voisines.iterrows():
            cl = len(lis & noms_top3(v["top3_lisibles"]))
            ci = len(imp & noms_top3(v["top3_imprevisibles"]))
            stable &= (cl >= 2) and (ci >= 2)
            details.append(f"{v['indice']} ≥{v['seuil']} ({v['n_wr_qualifies']} WR) : "
                           f"lisibles {cl}/3, imprévisibles {ci}/3 en commun")
        verdict = "STABLE (≥ 2/3 en commun avec chaque voisine)" if stable else "INSTABLE"
        print(f"\n{c['indice']} ≥{c['seuil']} | {c['choix']} | {c['pct_actions_eleve']} % d'actions élevées | "
              f"{c['n_wr_qualifies']} WR → {verdict}")
        print(f"  top 3 lisibles     : {c['top3_lisibles']}")
        print(f"  top 3 imprévisibles: {c['top3_imprevisibles']}")
        for d in details:
            print(f"  voisine {d}")
        lignes.append({"indice": c["indice"], "seuil": c["seuil"], "choix": c["choix"],
                       "pct_actions_eleve": c["pct_actions_eleve"], "n_wr_qualifies": c["n_wr_qualifies"],
                       "stabilite": verdict, "detail_voisines": " | ".join(details)})
    return pd.DataFrame(lignes)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    verifier_entrees()
    os.makedirs(SENS, exist_ok=True)
    m01 = charger_module("01_build_plays.py", "build_plays")
    m03 = charger_module("03_habitude.py", "habitude")

    actions = indices_enjeu(m01)
    noms = pd.read_csv(os.path.join(DATA, "players.csv"), usecols=["nflId", "displayName"])
    routes = pd.read_csv(os.path.join(OUT, "routes.csv")).merge(actions, on=["gameId", "playId"])
    routes["intention"] = routes["type_route"].map(INTENTION)       # NaN pour "Autre"
    print(f"Routes : {len(routes)} | dont hors 'Autre' (choix intention) : {routes['intention'].notna().sum()}")
    print("Répartition des intentions :",
          (routes["intention"].value_counts(normalize=True) * 100).round(1).to_dict())

    grille, tous = lancer_grille(routes, actions[actions["avec_lancer"]], m03, noms)

    pd.set_option("display.width", 250)
    print("\n=== Grille de sensibilité (minimum 20/20, 1 000 permutations, BH par combinaison) ===")
    print(grille.drop(columns=["top3_lisibles", "top3_imprevisibles"]).to_string(index=False))
    print("\nTop 3 par combinaison (score en points) :")
    for _, g in grille.iterrows():
        print(f"  {g['indice']} ≥{g['seuil']} {g['choix']:<10} | lisibles : {g['top3_lisibles']}")
        print(f"  {'':<16} | imprévisibles : {g['top3_imprevisibles']}")

    chemin = os.path.join(SENS, "grille.csv")
    grille.to_csv(chemin, index=False)
    print(f"\nÉcrit : {chemin} ({len(grille)} lignes)")
    chemin = os.path.join(SENS, "scores_toutes_combinaisons.csv")
    tous.to_csv(chemin, index=False)
    print(f"Écrit : {chemin} ({len(tous)} lignes)")

    rob = robustesse(tous, routes, noms)
    chemin = os.path.join(SENS, "robustesse.csv")
    rob.to_csv(chemin, index=False)
    print(f"\n=== Robustesse sur {len(grille)} combinaisons (top {TOP}) ===")
    vue = ["displayName", "n_combinaisons_qualifie", "n_top10_lisibles", "n_top10_imprevisibles",
           "part_touche_normal", "part_touche_eleve", "ecart_touche_pts"]
    print("10 WR le plus souvent dans le top 10 des plus lisibles :")
    print(rob.sort_values(["n_top10_lisibles", "n_combinaisons_qualifie"], ascending=False)[vue]
          .head(10).to_string(index=False))
    print("10 WR le plus souvent dans le top 10 des plus imprévisibles :")
    print(rob.sort_values(["n_top10_imprevisibles", "n_combinaisons_qualifie"], ascending=False)[vue]
          .head(10).to_string(index=False))
    print(f"Écrit : {chemin} ({len(rob)} lignes)")

    heatmap(grille, os.path.join(SENS, "sensibilite.png"))

    reco = recommandation(grille)
    if not reco.empty:
        chemin = os.path.join(SENS, "recommandation.csv")
        reco.to_csv(chemin, index=False)
        print(f"\nÉcrit : {chemin} ({len(reco)} lignes)")


if __name__ == "__main__":
    main()
