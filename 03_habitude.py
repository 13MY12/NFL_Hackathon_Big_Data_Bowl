"""
03_habitude.py — Score de lisibilité quand l'enjeu monte, par WR.

Entrées : outputs/routes.csv, outputs/plays_stakes.csv, data/players.csv
Sorties : outputs/score_wr_type_route.csv, outputs/score_wr_vs_marqueur.csv

Pour chaque WR qualifié (>= 30 routes en enjeu élevé ET >= 30 en enjeu normal ; 20/20 si < 60 WR) :
  habitude          = son choix le plus fréquent en enjeu normal (ex æquo : ordre alphabétique)
  taux_habitude_*   = part de ses routes égales à cette habitude, en enjeu normal / élevé
  variation         = taux_habitude_eleve - taux_habitude_normal
  score             = variation - moyenne des variations des WR qualifiés (> 0 : plus lisible)
  p_value           = test de permutation (1 000 tirages des étiquettes d'enjeu au sein du WR,
                      habitude recalculée à chaque tirage). Significatif si p < 0,05 (non corrigé) ;
                      la q-value de Benjamini-Hochberg est gardée en colonne pour information.

Remarque : l'habitude est choisie sur l'échantillon normal, donc son taux normal est gonflé et la
variation brute est négative en moyenne par construction. Le centrage du score et le test de
permutation (qui reproduit ce biais dans la distribution nulle) le corrigent.
"""

import os
import sys
import time
import numpy as np
import pandas as pd

RACINE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(RACINE, "data")
OUT = os.path.join(RACINE, "outputs")
N_PERM = 1000
GRAINE = 42
SEUIL_P = 0.05  # seuil de significativité sur la p-value brute (non corrigée)


def verifier_entrees():
    # Arrête le script si une entrée manque
    for chemin in [os.path.join(OUT, "routes.csv"), os.path.join(OUT, "plays_stakes.csv"),
                   os.path.join(DATA, "players.csv")]:
        if not os.path.exists(chemin):
            print(f"Fichier manquant : {chemin}")
            sys.exit(1)


def variations(codes, etiquettes, k):
    # Variation du taux d'habitude pour une matrice d'étiquettes (une ligne = un tirage)
    # codes : catégories triées alphabétiquement -> argmax renvoie la 1re (règle d'ex æquo)
    onehot = np.eye(k)[codes]                         # n_routes x k
    normal = (~etiquettes).astype(float) @ onehot     # comptes en enjeu normal, tirages x k
    eleve = onehot.sum(axis=0) - normal               # comptes en enjeu élevé
    h = normal.argmax(axis=1)                         # habitude de chaque tirage
    idx = np.arange(len(h))
    n_norm = (~etiquettes).sum(axis=1)
    n_elev = etiquettes.sum(axis=1)
    return eleve[idx, h] / n_elev - normal[idx, h] / n_norm


def benjamini_hochberg(p):
    # q-values de Benjamini-Hochberg
    p = np.asarray(p, dtype=float)
    n = len(p)
    ordre = np.argsort(p)
    q = p[ordre] * n / np.arange(1, n + 1)
    q = np.minimum(np.minimum.accumulate(q[::-1])[::-1], 1.0)
    sortie = np.empty(n)
    sortie[ordre] = q
    return sortie


def score_habitude(table, n_perm=N_PERM, graine=GRAINE, minimum_force=None):
    """Fonction générique. table : nflId, gameId, playId, choix, enjeu_eleve (booléen).
    minimum_force : si renseigné, minimum de routes imposé (pas de repli 30 -> 20).
    Renvoie (une ligne par WR qualifié, minimum de routes utilisé)."""
    comptes = table.groupby("nflId")["enjeu_eleve"].agg(n_eleve="sum", n_total="size")
    comptes["n_normal"] = comptes["n_total"] - comptes["n_eleve"]
    for minimum in ((minimum_force,) if minimum_force else (30, 20)):
        qualifies = comptes[(comptes["n_eleve"] >= minimum) & (comptes["n_normal"] >= minimum)]
        if len(qualifies) >= 60:
            break

    rng = np.random.default_rng(graine)
    groupes = dict(tuple(table[table["nflId"].isin(qualifies.index)].groupby("nflId")))
    lignes = []
    for nid in sorted(groupes):                       # ordre fixe -> p-values reproductibles
        d = groupes[nid]
        cats = np.array(sorted(d["choix"].astype(str).unique()))
        codes = np.searchsorted(cats, d["choix"].astype(str).values)
        lab = d["enjeu_eleve"].values.astype(bool)
        k = len(cats)

        # Valeurs observées
        n_norm_cat = np.bincount(codes[~lab], minlength=k)
        n_elev_cat = np.bincount(codes[lab], minlength=k)
        h = int(n_norm_cat.argmax())
        tn = n_norm_cat[h] / (~lab).sum()
        te = n_elev_cat[h] / lab.sum()
        var_obs = te - tn

        # Distribution nulle : on mélange les étiquettes d'enjeu au sein du WR
        perms = rng.permuted(np.tile(lab, (n_perm, 1)), axis=1)
        var_perm = variations(codes, perms, k)
        m = var_perm.mean()
        kk = int((np.abs(var_perm - m) >= np.abs(var_obs - m) - 1e-12).sum())
        lignes.append({
            "nflId": nid, "n_normal": int((~lab).sum()), "n_eleve": int(lab.sum()),
            "habitude": cats[h], "taux_habitude_normal": tn, "taux_habitude_eleve": te,
            "variation": var_obs, "p_value": (kk + 1) / (n_perm + 1),
        })

    res = pd.DataFrame(lignes)
    res["score_lisibilite_enjeu"] = res["variation"] - res["variation"].mean()
    res["q_value"] = benjamini_hochberg(res["p_value"])
    res["significatif"] = res["p_value"] < SEUIL_P
    return res, minimum


def lancer(routes, colonne, noms, fichier):
    # Applique la fonction générique à un choix et écrit le CSV
    debut = time.time()
    table = routes[["nflId", "gameId", "playId", colonne, "enjeu_eleve"]].rename(columns={colonne: "choix"})
    res, minimum = score_habitude(table)
    res = res.merge(noms, on="nflId", how="left")
    cols = ["nflId", "displayName", "n_normal", "n_eleve", "habitude", "taux_habitude_normal",
            "taux_habitude_eleve", "variation", "score_lisibilite_enjeu", "p_value", "q_value",
            "significatif"]
    res = res[cols].sort_values("score_lisibilite_enjeu", ascending=False)
    chemin = os.path.join(OUT, fichier)
    res.to_csv(chemin, index=False)

    print(f"\n=== Choix = {colonne} : lisibilité quand l'enjeu monte ===")
    print(f"Minimum de routes utilisé : {minimum}/{minimum}")
    print(f"WR qualifiés : {len(res)} (attendu ~83)")
    print(f"Variation brute moyenne : {res['variation'].mean():+.3f} (attendue négative, biais de construction)")
    print(f"Moyenne des scores : {res['score_lisibilite_enjeu'].mean():.1e} (attendue 0)")
    sig = res[res["significatif"]]
    print(f"WR significatifs (p < 0,05, non corrigé) : {len(sig)} "
          f"(dont {int((sig['score_lisibilite_enjeu'] > 0).sum())} plus lisibles, "
          f"{int((sig['score_lisibilite_enjeu'] < 0).sum())} plus imprévisibles) | "
          f"attendus par hasard : {SEUIL_P * len(res):.1f} | après Benjamini-Hochberg (q < 0,10) : "
          f"{int((res['q_value'] < 0.10).sum())}")
    vue = res[["displayName", "habitude", "taux_habitude_normal", "taux_habitude_eleve",
               "score_lisibilite_enjeu", "p_value", "q_value"]].round(3)
    print("5 plus lisibles quand l'enjeu monte :")
    print(vue.head(5).to_string(index=False))
    print("5 plus imprévisibles quand l'enjeu monte :")
    print(vue.tail(5).to_string(index=False))
    print(f"Permutations : {time.time() - debut:.1f} s")
    print(f"Écrit : {chemin} ({len(res)} lignes)")


def main():
    verifier_entrees()
    routes = pd.read_csv(os.path.join(OUT, "routes.csv"))
    enjeu = pd.read_csv(os.path.join(OUT, "plays_stakes.csv"), usecols=["gameId", "playId", "enjeu_eleve"])
    routes = routes.merge(enjeu, on=["gameId", "playId"], how="inner")
    routes["enjeu_eleve"] = routes["enjeu_eleve"].astype(bool)
    print(f"Routes : {len(routes)} | part en enjeu élevé : {routes['enjeu_eleve'].mean():.1%}")
    noms = pd.read_csv(os.path.join(DATA, "players.csv"), usecols=["nflId", "displayName"])

    lancer(routes, "type_route", noms, "score_wr_type_route.csv")
    lancer(routes, "vs_marqueur", noms, "score_wr_vs_marqueur.csv")


if __name__ == "__main__":
    main()
