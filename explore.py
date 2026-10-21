"""
explore.py — Faisabilite de l'idee "Les receveurs deviennent-ils previsibles
quand l'enjeu monte ?" (NFL Big Data Bowl).

Ne lit que 10 fichiers de tracking max. Produit uniquement des CHIFFRES dans la
console (aucun fichier ecrit). Sert a valider les hypotheses avant d'ecrire les
scripts finaux 01_..05_.
"""

import os
import glob
import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(__file__), "data")
TRACK_DIR = os.path.join(DATA, "tracking")
MAX_FILES = 10
WR_TE_RB = {"WR", "TE", "RB"}


def sep(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


# ---------------------------------------------------------------------------
# Chargement des tables de reference
# ---------------------------------------------------------------------------
plays = pd.read_csv(os.path.join(DATA, "plays.csv"))
players = pd.read_csv(os.path.join(DATA, "players.csv"))
pff = pd.read_csv(os.path.join(DATA, "pffScoutingData.csv"))
games = pd.read_csv(os.path.join(DATA, "games.csv"))

sep("TAILLES DES TABLES")
print(f"plays   : {len(plays):>8} lignes")
print(f"players : {len(players):>8} lignes")
print(f"pff     : {len(pff):>8} lignes")
print(f"games   : {len(games):>8} lignes")
print(f"fichiers tracking disponibles : {len(glob.glob(os.path.join(TRACK_DIR, '*.csv')))}")

# ---------------------------------------------------------------------------
# A. pff_role + positions
# ---------------------------------------------------------------------------
sep("A1. pff_role (valeurs uniques)")
print(pff["pff_role"].value_counts())

sep("A1b. positions des Pass Route (pff_positionLinedUp)")
routes = pff[pff["pff_role"] == "Pass Route"]
print(routes["pff_positionLinedUp"].value_counts().head(20))

# Position officielle des joueurs en Pass Route (WR/TE/RB)
pos = players.set_index("nflId")["officialPosition"]
routes = routes.copy()
routes["officialPosition"] = routes["nflId"].map(pos)
sep("A1c. officialPosition des joueurs en Pass Route")
print(routes["officialPosition"].value_counts())
n_route_wrteRB = routes[routes["officialPosition"].isin(WR_TE_RB)].shape[0]
print(f"\nRoutes WR/TE/RB (toutes semaines) : {n_route_wrteRB}")

# ---------------------------------------------------------------------------
# B. absoluteYardlineNumber — sens
# ---------------------------------------------------------------------------
sep("B. absoluteYardlineNumber : stats + lien avec yardlineNumber/yardlineSide")
print(plays[["absoluteYardlineNumber", "yardlineNumber", "yardlineSide",
             "possessionTeam"]].describe(include="all").T)
print("\nExemples:")
print(plays[["possessionTeam", "yardlineSide", "yardlineNumber",
             "absoluteYardlineNumber"]].head(8).to_string(index=False))

# ---------------------------------------------------------------------------
# C. Indice d'enjeu (stakes) — calcule sur TOUTES les plays
# ---------------------------------------------------------------------------
sep("C. INDICE D'ENJEU (sur toutes les plays)")
p = plays.copy()


def clock_to_sec(gc):
    try:
        m, s = str(gc).split(":")
        return int(m) * 60 + int(s)
    except Exception:
        return np.nan


p["clock_sec"] = p["gameClock"].map(clock_to_sec)
p["score_diff"] = (p["preSnapHomeScore"] - p["preSnapVisitorScore"]).abs()

# yards depuis la ligne de but adverse : red zone si l'equipe en possession
# est a <= 20 yards de la end zone. yardlineSide != possessionTeam => terrain adverse.
own_half = p["yardlineSide"] == p["possessionTeam"]
yards_to_goal = np.where(own_half, 100 - p["yardlineNumber"], p["yardlineNumber"])
p["yards_to_goal"] = yards_to_goal

stakes = (
    (p["down"] == 3).astype(int) * 1
    + (p["down"] == 4).astype(int) * 2
    + (p["yardsToGo"] >= 7).astype(int) * 1
    + (p["quarter"] >= 4).astype(int) * 1
    + (p["score_diff"] <= 8).astype(int) * 1
    + (p["clock_sec"] <= 120).astype(int) * 1
    + (p["yards_to_goal"] <= 20).astype(int) * 1
)
p["stakes"] = stakes
print("Distribution de l'indice d'enjeu :")
print(p["stakes"].value_counts().sort_index())
q75 = p["stakes"].quantile(0.75)
print(f"\nSeuil 75e percentile (enjeu eleve >=) : {q75}")
print(f"Part de plays a enjeu eleve : {(p['stakes'] >= q75).mean():.1%}")

# ---------------------------------------------------------------------------
# D. Lecture de 10 fichiers de tracking
# ---------------------------------------------------------------------------
sep("D. TRACKING (echantillon de 10 fichiers)")
files = sorted(glob.glob(os.path.join(TRACK_DIR, "*.csv")))[:MAX_FILES]
print("Fichiers lus :")
for f in files:
    print("  ", os.path.basename(f))

tr = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
print(f"\nLignes tracking chargees : {len(tr):,}")

sep("D1. event (valeurs uniques dans l'echantillon)")
print(tr["event"].value_counts().head(30))

# Le tracking continue-t-il apres pass_forward ?
sep("D2. Le tracking continue-t-il apres pass_forward ?")
# pour chaque (gameId, playId) regarde le frameId du pass_forward vs frame max
grp = tr.groupby(["gameId", "playId"])
pf = tr[tr["event"] == "pass_forward"][["gameId", "playId", "frameId"]]
pf = pf.rename(columns={"frameId": "pf_frame"}).drop_duplicates(["gameId", "playId"])
maxf = grp["frameId"].max().rename("max_frame").reset_index()
m = pf.merge(maxf, on=["gameId", "playId"])
m["frames_after"] = m["max_frame"] - m["pf_frame"]
print(f"Plays avec pass_forward (echantillon)   : {len(m)}")
print(f"Frames apres pass_forward (describe):")
print(m["frames_after"].describe())

# ---------------------------------------------------------------------------
# E. Familles de routes sur l'echantillon
# ---------------------------------------------------------------------------
sep("E. FAMILLES DE ROUTES (echantillon)")
# jointure tracking <-> pff (role) <-> plays (playDirection via tracking)
route_keys = routes[["gameId", "playId", "nflId", "officialPosition"]]
route_keys = route_keys[route_keys["officialPosition"].isin(WR_TE_RB)]

trr = tr.merge(route_keys, on=["gameId", "playId", "nflId"], how="inner")
print(f"Lignes tracking de receveurs en route (echantillon) : {len(trr):,}")

# pour chaque play/joueur : position au ball_snap et au pass_forward
def family_for_group(g):
    g = g.sort_values("frameId")
    snap = g[g["event"] == "ball_snap"]
    fwd = g[g["event"] == "pass_forward"]
    if snap.empty or fwd.empty:
        return None
    direction = g["playDirection"].iloc[0]
    xs, ys = snap["x"].iloc[0], snap["y"].iloc[0]
    xf, yf = fwd["x"].iloc[0], fwd["y"].iloc[0]
    # normalisation : offense avance toujours vers +x ; y: cote vers +y
    if direction == "left":
        dx = xs - xf   # profondeur (downfield positif)
        dy = yf - ys
    else:
        dx = xf - xs
        dy = yf - ys
    depth = "courte" if dx < 5 else ("moyenne" if dx <= 15 else "profonde")
    # interieur/exterieur : vers le centre du terrain (y=26.65) = interieur
    center = 26.65
    moving_in = (yf - center) * (ys - center) < 0 or abs(yf - center) < abs(ys - center)
    side = "interieur" if moving_in else "exterieur"
    return f"{depth}_{side}", dx, dy


fams = []
depths = []
for (gid, pid, nid), g in trr.groupby(["gameId", "playId", "nflId"]):
    r = family_for_group(g)
    if r:
        fams.append(r[0])
        depths.append(r[1])

fams = pd.Series(fams)
sep("E1. Repartition des familles de routes (echantillon)")
print(fams.value_counts())
print(f"\nRoutes exploitables (snap+forward presents) : {len(fams)}")
if depths:
    print("\nProfondeur dx (yards downfield) describe:")
    print(pd.Series(depths).describe())

# ---------------------------------------------------------------------------
# F. Extrapolation : WR avec >=20 routes a enjeu eleve
# ---------------------------------------------------------------------------
sep("F. EXTRAPOLATION aux 122 matchs")
n_files_total = len(glob.glob(os.path.join(TRACK_DIR, "*.csv")))
scale = n_files_total / len(files)
routes_ech = len(fams)
print(f"Routes exploitables echantillon : {routes_ech}")
print(f"Facteur d'echelle (122/{len(files)}) : {scale:.1f}")
print(f"Routes exploitables estimees (total) : {routes_ech * scale:,.0f}")

# receveurs distincts dans l'echantillon et routes/joueur
counts = (
    trr[trr["event"] == "ball_snap"]
    .drop_duplicates(["gameId", "playId", "nflId"])
    .groupby("nflId").size()
)
print(f"\nReceveurs distincts (echantillon) : {counts.shape[0]}")
print(f"Routes/joueur median (echantillon) : {counts.median():.0f}")
print(f"Estimation routes/joueur sur saison (x{scale:.0f}, grossier) : "
      f"{counts.median() * scale:.0f}")


# ---------------------------------------------------------------------------
# G. Routes a enjeu eleve par joueur (jointure routes <-> stakes) + seuil 25%
# ---------------------------------------------------------------------------
sep("G. ROUTES A ENJEU ELEVE PAR JOUEUR")

# Deux definitions d'enjeu eleve : (a) >=75e pct (>=3), (b) strict top 25% reel
thr_a = q75                      # 3.0 -> capture 39%
# seuil qui approche 25% : on prend la valeur telle que part <= ~25%
for cand in sorted(p["stakes"].unique(), reverse=True):
    if (p["stakes"] >= cand).mean() >= 0.25:
        thr_b = cand
        break
print(f"Seuil 'eleve' (>=3, ~39%)        : part {(p['stakes']>=3).mean():.1%}")
print(f"Seuil 'eleve' strict ~25% (>= {thr_b}) : part {(p['stakes']>=thr_b).mean():.1%}")

# plays a enjeu eleve (def stricte) -> jointure avec les routes WR/TE/RB (toutes semaines)
high_plays = p.loc[p["stakes"] >= thr_b, ["gameId", "playId"]]
routes_all = routes[routes["officialPosition"].isin(WR_TE_RB)][
    ["gameId", "playId", "nflId", "officialPosition"]
]
routes_high = routes_all.merge(high_plays, on=["gameId", "playId"], how="inner")
low_plays = p.loc[p["stakes"] < thr_b, ["gameId", "playId"]]
routes_low = routes_all.merge(low_plays, on=["gameId", "playId"], how="inner")

n_high = routes_high.groupby("nflId").size()
n_low = routes_low.groupby("nflId").size()
joined = pd.DataFrame({"high": n_high, "low": n_low}).fillna(0)
print(f"\nReceveurs WR/TE/RB distincts (toutes semaines)      : {routes_all['nflId'].nunique()}")
print(f"Receveurs avec >=20 routes a ENJEU ELEVE (reel data) : {(joined['high']>=20).sum()}")
print(f"Receveurs avec >=20 routes high ET >=20 low          : "
      f"{((joined['high']>=20)&(joined['low']>=20)).sum()}")
print(f"Receveurs avec >=30 high ET >=30 low                 : "
      f"{((joined['high']>=30)&(joined['low']>=30)).sum()}")

# WR seuls
wr_ids = set(players.loc[players['officialPosition']=='WR','nflId'])
jwr = joined[joined.index.isin(wr_ids)]
print(f"\nWR seuls avec >=20 high ET >=20 low                  : "
      f"{((jwr['high']>=20)&(jwr['low']>=20)).sum()}")
