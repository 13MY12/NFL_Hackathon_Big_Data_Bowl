"""
app.py — Démo interactive « Les receveurs deviennent-ils prévisibles quand l'enjeu monte ? »

Lit uniquement des fichiers déjà calculés (aucun recalcul lourd). Chaque fichier est cherché dans
outputs/final/, puis outputs/, puis outputs/sensibilite/ ; un élément n'est affiché que si son
fichier existe.

Installation : py -m pip install streamlit plotly
Lancement    : py -m streamlit run app.py
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

RACINE = os.path.dirname(os.path.abspath(__file__))
DOSSIERS = [os.path.join(RACINE, "outputs", "final"), os.path.join(RACINE, "outputs"),
            os.path.join(RACINE, "outputs", "sensibilite")]
CLES = ["gameId", "playId", "nflId"]
SEUIL = 4

GRIS, ROUGE, VIOLET, VERT = "#9e9e9e", "#d62728", "#7b2cbf", "#2a9d8f"
COUL_INT = {"Jeu rapide": "#f4a261", "Vers la touche": "#1f77b4",
            "Vers le milieu": "#9467bd", "Vertical": "#e63946"}
INTENTIONS = list(COUL_INT)
INTENTION = {"Flat/Screen": "Jeu rapide", "Slant": "Jeu rapide", "Retour": "Jeu rapide",
             "Out": "Vers la touche", "Corner": "Vers la touche",
             "In/Dig": "Vers le milieu", "Post": "Vers le milieu", "Go": "Vertical"}  # Autre exclu
CONSEIL = {"Vers la touche": "jouer son côté extérieur", "Vers le milieu": "fermer l'intérieur",
           "Vertical": "garder un safety profond", "Jeu rapide": "presser à la ligne"}


# --- Accès aux fichiers -----------------------------------------------------------------------
def chemin(nom):
    # Premier emplacement où le fichier existe, sinon None
    for d in DOSSIERS:
        p = os.path.join(d, nom)
        if os.path.exists(p):
            return p
    return None


@st.cache_data(show_spinner=False)
def lire_csv(nom, colonnes=None):
    # Lecture mise en cache (une seule fois par session serveur)
    p = chemin(nom)
    return pd.read_csv(p, usecols=colonnes) if p else None


@st.cache_data(show_spinner=False)
def routes_avec_enjeu():
    # routes.csv + indice d'enjeu, type de route -> intention ("Autre" exclu)
    routes = lire_csv("routes.csv", ["gameId", "playId", "nflId", "type_route"])
    jeu = lire_csv("plays_stakes.csv", ["gameId", "playId", "indice_enjeu"])
    if routes is None or jeu is None:
        return None
    r = routes.merge(jeu, on=["gameId", "playId"])
    r["intention"] = r["type_route"].map(INTENTION)
    r = r[r["intention"].notna()].copy()
    r["enjeu_eleve"] = r["indice_enjeu"] >= SEUIL
    return r


@st.cache_data(show_spinner=False)
def trajectoires():
    # Trajectoires en types compacts pour un filtrage rapide
    t = lire_csv("trajectoires.csv", CLES + ["frame_rel", "ecart_ballon", "profondeur"])
    if t is not None:
        t = t.astype({"frame_rel": "int16", "ecart_ballon": "float32", "profondeur": "float32"})
    return t


def image(nom, legende=None):
    # Affiche une image seulement si elle existe
    p = chemin(nom)
    if p:
        st.image(p, caption=legende, width="stretch")
    return p is not None


def fr(x, d=1, signe=False):
    # Nombre au format français
    s = f"{x:+.{d}f}" if signe else f"{x:.{d}f}"
    return s.replace(".", ",")


def milliers(n):
    # 20415 -> "20 415"
    return f"{n:,}".replace(",", " ")


def style_plotly(fig, hauteur=420):
    # Thème sombre, fond transparent
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      height=hauteur, margin=dict(l=10, r=10, t=40, b=10), font=dict(size=14, color="white"),
                      legend=dict(bgcolor="rgba(0,0,0,0)"))
    return fig


def carte(html):
    # Section en carte translucide
    st.markdown(f'<div class="carte">{html}</div>', unsafe_allow_html=True)


# --- Style ------------------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Lisibles quand l'enjeu monte ?", page_icon="🏈")
st.markdown("""
<style>
.stApp {
  background:
    repeating-linear-gradient(0deg, rgba(255,255,255,0.06) 0px, rgba(255,255,255,0.06) 2px,
                              transparent 2px, transparent 90px),
    linear-gradient(180deg, #0b1d3a 0%, #1f5130 100%);
  background-attachment: fixed;
  color: #ffffff;
}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3 { color: #ffffff; }
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"] { visibility: hidden; }
.block-container { padding-top: 2rem; max-width: 1400px; }
.carte, div[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(255,255,255,0.08); border-radius: 16px; padding: 24px; margin-bottom: 18px;
  border: 1px solid rgba(255,255,255,0.12);
}
.heros h1 { font-size: 3rem; line-height: 1.15; margin-bottom: 0.3rem; }
.heros .sous { font-size: 1.15rem; opacity: 0.85; }
.metrique { background: rgba(255,255,255,0.08); border-radius: 16px; padding: 22px; text-align: center;
            border: 1px solid rgba(255,255,255,0.12); height: 100%; }
.metrique .val { font-size: 2.8rem; font-weight: 800; line-height: 1.1; }
.metrique .lib { font-size: 1.05rem; opacity: 0.85; margin-top: 6px; }
[data-testid="stMetricValue"] { font-size: 2.2rem; font-weight: 800; color: #ffffff; }
[data-testid="stMetricLabel"] p { font-size: 1rem; opacity: 0.85; }
.intention { border-radius: 14px; padding: 18px; color: #ffffff; font-size: 1.05rem; height: 100%; }
.intention b { font-size: 1.25rem; }
.bandeau { background: rgba(123,44,191,0.35); border-left: 6px solid #7b2cbf; border-radius: 12px;
           padding: 14px 18px; font-size: 1.15rem; font-weight: 600; margin: 8px 0 14px 0; }
.conseil { background: #fff3cd; color: #222 !important; border-radius: 12px; padding: 16px 20px;
           font-size: 1.2rem; font-weight: 700; border: 2px solid #d4a017; margin-top: 10px; }
.badge { display: inline-block; background: #7b2cbf; border-radius: 999px; padding: 4px 14px;
         font-weight: 700; margin-left: 8px; }
.pied { text-align: center; opacity: 0.7; padding: 24px 0 8px 0; }
table.enjeu { width: 100%; border-collapse: collapse; font-size: 1.05rem; }
table.enjeu td { padding: 7px 10px; border-bottom: 1px solid rgba(255,255,255,0.15); }
table.enjeu td:last-child { text-align: right; font-weight: 700; }
button[data-baseweb="tab"] p { font-size: 1.05rem; }
</style>
""", unsafe_allow_html=True)

scores = lire_csv("score_wr_intention.csv")
rob = lire_csv("robustesse.csv")
r_enjeu = routes_avec_enjeu()

# --- 1. Héros ---------------------------------------------------------------------------------
st.markdown('<div class="heros"><h1>Les receveurs deviennent-ils prévisibles quand l\'enjeu monte ?</h1>'
            '<div class="sous">NFL Big Data Bowl – Paris Side Quest | tracking Next Gen Stats + PFF, '
            'saison 2021 sem. 1-8</div></div>', unsafe_allow_html=True)
st.write("")
routes_brutes = lire_csv("routes.csv", ["nflId"])
n_routes = milliers(len(routes_brutes)) if routes_brutes is not None else "20 415"
n_wr = len(scores) if scores is not None else 104
n_p = int((scores["p_value"] < 0.05).sum()) if scores is not None else 10
c1, c2, c3 = st.columns(3)
for col, val, lib in [(c1, n_routes, "routes de WR"), (c2, str(n_wr), "WR comparés"),
                      (c3, str(n_p), f"WR changent nettement (≈{round(0.05 * n_wr)} attendus par hasard, p ≈ 0,04)")]:
    col.markdown(f'<div class="metrique"><div class="val">{val}</div><div class="lib">{lib}</div></div>',
                 unsafe_allow_html=True)
st.write("")

# --- 2. La question ---------------------------------------------------------------------------
carte("<h2>La question</h2><p style='font-size:1.15rem'>Sur les actions décisives, un receveur retombe-t-il "
      "dans ses habitudes ? Si oui, la défense peut l'anticiper. On mesure, pour chaque WR, s'il répète plus "
      "son habitude quand l'enjeu monte, comparé aux autres WR.</p>")

# --- 3. Le système d'enjeu --------------------------------------------------------------------
with st.container(border=True):
    st.markdown("## Le système d'enjeu")
    g, d = st.columns([1, 1.3])
    criteres = [("3e tentative", "+1"), ("4e tentative", "+2"), ("7 yards ou plus à faire", "+1"),
                ("4e quart-temps", "+1"), ("Écart de score ≤ 8 points", "+2"),
                ("Moins de 2 min dans la mi-temps", "+1"), ("Zone rouge (≤ 20 yards de l'en-but)", "+1")]
    g.markdown('<table class="enjeu">' + "".join(f"<tr><td>{c}</td><td>{p}</td></tr>" for c, p in criteres)
               + "</table>", unsafe_allow_html=True)
    g.markdown("**Enjeu élevé = indice ≥ 4, soit 30 % des actions.**")
    jeu = lire_csv("plays_stakes.csv", ["indice_enjeu"])
    if jeu is not None:
        dist = jeu["indice_enjeu"].value_counts().sort_index()
        fig = go.Figure(go.Bar(x=dist.index, y=dist.values,
                               marker_color=[ROUGE if i >= SEUIL else GRIS for i in dist.index],
                               hovertemplate="indice %{x} : %{y} actions<extra></extra>"))
        fig.update_layout(title="Répartition des actions selon l'indice d'enjeu",
                          xaxis_title="Indice d'enjeu", yaxis_title="Nombre d'actions", xaxis=dict(dtick=1))
        d.plotly_chart(style_plotly(fig, 360), width="stretch")

# --- 4. Les routes ----------------------------------------------------------------------------
with st.container(border=True):
    st.markdown("## Les routes")
    st.markdown("Chaque route est reconstruite à partir des positions x/y du receveur entre le snap et le "
                "lancer, mesurées 10 fois par seconde. Sa profondeur et son déplacement latéral donnent un type "
                "de route, regroupé ici en 4 intentions.")
    regroupe = {"Jeu rapide": "Flat/Screen, Slant, Retour", "Vers la touche": "Out, Corner",
                "Vers le milieu": "In/Dig, Post", "Vertical": "Go"}
    for col, (nom, types) in zip(st.columns(4), regroupe.items()):
        col.markdown(f'<div class="intention" style="background:{COUL_INT[nom]}"><b>{nom}</b><br>{types}</div>',
                     unsafe_allow_html=True)
    if chemin("grille_routes.png"):
        with st.expander("Voir des exemples de routes"):
            image("grille_routes.png")

# --- 5. Le score de lisibilité ----------------------------------------------------------------
exemple = ""
if scores is not None and (scores["displayName"] == "Mike Evans").any():
    e = scores[scores["displayName"] == "Mike Evans"].iloc[0]
    exemple = (f"<p><b>Exemple : Mike Evans.</b> Habitude = « {e['habitude']} ». En enjeu normal, "
               f"{fr(e['taux_habitude_normal'] * 100, 0)} % de ses routes ; en enjeu élevé, "
               f"{fr(e['taux_habitude_eleve'] * 100, 0)} %. Score = {fr(e['score_lisibilite_enjeu'] * 100, 1, True)} pts "
               f"au-dessus de la moyenne des WR.</p>")
carte("<h2>Le score de lisibilité</h2><ul style='font-size:1.1rem'>"
      "<li><b>Habitude</b> = intention la plus fréquente en enjeu normal.</li>"
      "<li><b>Score</b> = (part de l'habitude en enjeu élevé − en normal) − moyenne des WR.</li>"
      "<li><b>Test de permutation</b>, 1000 tirages : on mélange les étiquettes d'enjeu pour voir si l'écart "
      "dépasse le hasard.</li></ul>" + exemple)

# --- 6. Cas d'usage ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown("## Cas d'usage")
    onglets = [("Mike Evans (TB)", "fiche_Mike_Evans.png",
                "Vers la touche : 38 % → 51 % → jouer son côté extérieur | top 10 dans 8 des 9 combinaisons testées"),
               ("Brandon Aiyuk (SF)", "fiche_Brandon_Aiyuk.png",
                "Vers la touche : 29 % → 59 % → jouer son côté extérieur | top 10 dans 6 des 8 combinaisons")]
    onglets = [o for o in onglets if chemin(o[1])]
    if onglets:
        for tab, (_, fichier, bandeau) in zip(st.tabs([o[0] for o in onglets]), onglets):
            with tab:
                st.markdown(f'<div class="bandeau">{bandeau}</div>', unsafe_allow_html=True)
                image(fichier)

# --- 7. Explorer un receveur ------------------------------------------------------------------
if scores is not None:
    with st.container(border=True):
        st.markdown("## Explorer un receveur")
        noms = sorted(scores["displayName"].dropna().unique())
        nom = st.selectbox("Choisir un WR", noms, index=noms.index("Mike Evans") if "Mike Evans" in noms else 0)
        wr = scores[scores["displayName"] == nom].iloc[0]

        # a) métriques
        badge = '<span class="badge">◆ tendance</span>' if wr["p_value"] < 0.05 else ""
        st.markdown(f"### {nom} {badge}", unsafe_allow_html=True)
        m = st.columns(6)
        m[0].metric("Équipe", wr.get("equipe", "?"))
        m[1].metric("Routes normal", int(wr["n_normal"]))
        m[2].metric("Routes élevé", int(wr["n_eleve"]))
        m[3].metric("Habitude", wr["habitude"])
        m[4].metric("Score", f"{fr(wr['score_lisibilite_enjeu'] * 100, 1, True)} pts")
        m[5].metric("p-value", fr(wr["p_value"], 3))
        if rob is not None and (rob["nflId"] == wr["nflId"]).any():
            rb = rob[rob["nflId"] == wr["nflId"]].iloc[0]
            st.caption(f"Robustesse : top 10 des plus lisibles dans {int(rb['n_top10_lisibles'])} et des plus "
                       f"imprévisibles dans {int(rb['n_top10_imprevisibles'])} des "
                       f"{int(rb['n_combinaisons_qualifie'])} combinaisons où il est qualifié.")

        if r_enjeu is not None:
            r = r_enjeu[r_enjeu["nflId"] == wr["nflId"]]
            parts = {e: r[r["enjeu_eleve"] == e]["intention"].value_counts(normalize=True)
                         .reindex(INTENTIONS, fill_value=0) * 100 for e in (False, True)}
            g, d = st.columns([1, 1])

            # b) barres groupées
            fig = go.Figure()
            for e, coul, lib in [(False, GRIS, "Enjeu normal"), (True, ROUGE, "Enjeu élevé")]:
                fig.add_bar(x=INTENTIONS, y=parts[e].values, name=lib, marker_color=coul,
                            text=[f"{v:.0f} %" for v in parts[e].values], textposition="outside",
                            hovertemplate="%{x} : %{y:.1f} %<extra>" + lib + "</extra>")
            fig.update_layout(barmode="group", title="Part de chaque intention", yaxis_title="% de ses routes",
                              yaxis=dict(range=[0, max(parts[False].max(), parts[True].max()) * 1.25]),
                              legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))
            g.plotly_chart(style_plotly(fig, 470), width="stretch")

            # c) carte de routes interactive
            traj = trajectoires()
            with d:
                choix = st.radio("Niveau d'enjeu", ["Enjeu normal", "Enjeu élevé"], horizontal=True)
                if traj is not None:
                    sel = r[r["enjeu_eleve"] == (choix == "Enjeu élevé")]
                    sel = sel.sample(min(40, len(sel)), random_state=42)
                    t = traj[traj["nflId"] == wr["nflId"]].merge(sel[CLES + ["intention"]], on=CLES)
                    fig = go.Figure()
                    vus = set()
                    for _, tt in t.groupby(CLES):
                        tt = tt.sort_values("frame_rel")
                        it = tt["intention"].iloc[0]
                        fig.add_scatter(x=tt["ecart_ballon"], y=tt["profondeur"], mode="lines",
                                        line=dict(color=COUL_INT[it], width=3), name=it, legendgroup=it,
                                        showlegend=it not in vus, hovertemplate=it + "<extra></extra>")
                        fig.add_scatter(x=[tt["ecart_ballon"].iloc[-1]], y=[tt["profondeur"].iloc[-1]],
                                        mode="markers", marker=dict(color=COUL_INT[it], size=8,
                                                                    line=dict(color="white", width=1)),
                                        legendgroup=it, showlegend=False, hoverinfo="skip")
                        vus.add(it)
                    for yd in range(-5, 45, 5):
                        fig.add_hline(y=yd, line=dict(color="rgba(255,255,255,0.25)", width=1))
                    fig.add_hline(y=0, line=dict(color="white", width=4))
                    fig.add_scatter(x=[0], y=[0], mode="markers", marker=dict(color="#8b4513", size=13,
                                    line=dict(color="white", width=2)), name="Ballon", hoverinfo="skip")
                    style_plotly(fig, 470)
                    fig.update_layout(plot_bgcolor="#2e6b34",
                                      title=f"{len(sel)} routes tirées au hasard ({choix.lower()})",
                                      xaxis_title="Distance au ballon (yards), ligne de touche à droite",
                                      yaxis_title="Yards au-delà de la ligne de mêlée",
                                      xaxis=dict(showgrid=False, zeroline=False),
                                      yaxis=dict(showgrid=False, zeroline=False),
                                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))
                    st.plotly_chart(fig, width="stretch")

            # d) phrase automatique
            ecart = parts[True] - parts[False]
            monte, baisse = ecart.idxmax(), ecart.idxmin()
            st.markdown(f'<div class="conseil">Quand l\'enjeu monte, {nom} remplace « {baisse} » '
                        f'({parts[False][baisse]:.0f} % → {parts[True][baisse]:.0f} %) par « {monte} » '
                        f'({parts[False][monte]:.0f} % → {parts[True][monte]:.0f} %) → {CONSEIL[monte]}</div>',
                        unsafe_allow_html=True)

# --- 8. Vue d'ensemble ------------------------------------------------------------------------
with st.container(border=True):
    st.markdown("## Vue d'ensemble")
    t1, t2, t3 = st.tabs(["Classement", "Tous les WR", "Robustesse"])
    with t1:
        if not image("classement.png"):
            st.info("classement.png introuvable")
    with t2:
        if scores is not None:
            x, y = scores["taux_habitude_normal"] * 100, scores["taux_habitude_eleve"] * 100
            decal = scores["variation"].mean() * 100
            bas, haut = min(x.min(), y.min()) - 3, max(x.max(), y.max()) + 3
            fig = go.Figure()
            fig.add_scatter(x=[bas, haut], y=[bas, haut], mode="lines", line=dict(color="white", width=1.5),
                            name="Même fidélité dans les deux cas", hoverinfo="skip")
            fig.add_scatter(x=[bas, haut], y=[bas + decal, haut + decal], mode="lines",
                            line=dict(color="white", width=1.5, dash="dash"),
                            name=f"Tendance moyenne ({fr(decal, 1, True)} pts)", hoverinfo="skip")
            for signe, coul, lib in [(True, VIOLET, "Plus lisible"), (False, VERT, "Plus imprévisible")]:
                s = scores[(scores["score_lisibilite_enjeu"] > 0) == signe]
                fig.add_scatter(
                    x=s["taux_habitude_normal"] * 100, y=s["taux_habitude_eleve"] * 100, mode="markers",
                    name=lib, marker=dict(color=coul, size=11, line=dict(color="white", width=1),
                                          symbol=np.where(s["p_value"] < 0.05, "diamond", "circle")),
                    customdata=np.stack([s["displayName"], s["habitude"], s["score_lisibilite_enjeu"] * 100,
                                         s["p_value"]], axis=-1),
                    hovertemplate="<b>%{customdata[0]}</b><br>habitude : %{customdata[1]}<br>"
                                  "normal %{x:.0f} % → élevé %{y:.0f} %<br>score %{customdata[2]:+.1f} pts"
                                  "<br>p = %{customdata[3]:.3f}<extra></extra>")
            style_plotly(fig, 620)
            fig.update_layout(xaxis_title="Part des routes qui suivent son habitude, enjeu normal (%)",
                              yaxis_title="Part des routes qui suivent son habitude, enjeu élevé (%)",
                              xaxis=dict(range=[bas, haut]), yaxis=dict(range=[bas, haut], scaleanchor="x"),
                              title="Un point par WR (◆ = tendance, p < 0,05)")
            st.plotly_chart(fig, width="stretch")
    with t3:
        image("sensibilite.png")
        st.markdown("Les classements varient selon les paramètres, mais **Evans, Aiyuk, Sanders et M. Brown** "
                    "ressortent dans la majorité des 12 combinaisons.")

# --- 9. Limites et suite ----------------------------------------------------------------------
carte("<h2>Limites et suite</h2><ul style='font-size:1.1rem'>"
      "<li><b>8 semaines de données</b> seulement (saison 2021, semaines 1 à 8).</li>"
      "<li><b>Route observée jusqu'au lancer</b> : le tracking s'arrête environ 0,5 s après la passe.</li>"
      "<li><b>Résultats individuels non significatifs après correction</b> pour tests multiples, "
      "d'où le vocabulaire « tendance ».</li></ul>"
      "<p style='font-size:1.15rem'>→ Avec une saison complète : une <b>fiche de scouting automatique</b> pour "
      "chaque receveur adverse.</p>")

st.markdown('<div class="pied">Fait avec Kiro | Données NFL Next Gen Stats + PFF</div>', unsafe_allow_html=True)
