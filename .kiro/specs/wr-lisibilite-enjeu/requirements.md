# Requirements Document

## Introduction

Document d'exigences de la feature wr-lisibilite-enjeu. Chaque receveur écarté (WR) a ses habitudes de routes. L'analyse mesure, pour tous les WR de la saison 2021 (semaines 1 à 8, actions de passe), si un WR s'accroche davantage à son habitude quand l'enjeu monte (lisible pour la défense) ou s'en éloigne (imprévisible), puis l'illustre sur un joueur. Public : coordinateur défensif (fiche de tendance) et commentateur TV.

Contexte de livraison : hackathon de 3 h, gel du code à 15h15, soumission à 15h45. Livrable : 5 scripts Python autonomes et un README, sans application web ni framework de tests. Ordre de réalisation : P0, puis P1, puis P2.

Faits mesurés sur le dataset (références pour les contrôles console) :

| Fait | Valeur |
|---|---|
| Actions dans plays.csv | 8 557 (C 4 620, I 2 755, IN 190, S 543, R 449), dont 7 565 avec lancer |
| Prolongation (quarter = 5) | 98 actions |
| yardlineSide vide | 125 actions |
| Tracking, 10 matchs | 769 actions, 3 sans snap, 69 sans lancer, 8 récupérées par autoevent_passforward |
| Durée snap → lancer | médiane 26 frames (2,6 s), min 13, max 98 |
| Fin du tracking | ≤ 5 frames après le lancer |
| Profondeur médiane du WR au snap | −0,85 yd |
| Lecture du tracking | 10 fichiers ≈ 2 s |
| Routes de WR sur actions avec lancer | 20 374 routes, 209 WR distincts |
| Seuils d'enjeu élevé (part des actions / WR qualifiés 30/30) | ≥ 3 : 68,1 % / 87 ; ≥ 4 : 29,1 % / 83 ; ≥ 5 : 7,7 % / 5 |

## Glossary

- **Pipeline** : scripts 01 à 05 à la racine du dépôt.
- **Script_Enjeu** : 01_build_plays.py.
- **Extracteur_Routes** : 02_extract_routes.py.
- **Calculateur_Habitude** : 03_habitude.py.
- **Modele_Bonus** : 04_model.py.
- **Visualiseur** : 05_viz.py.
- **README** : README.md à la racine.
- **WR** : joueur avec officialPosition = "WR" (players.csv) et pff_role = "Pass Route" sur l'action (pffScoutingData.csv).
- **Frame_Snap** : frame de l'événement ball_snap, sinon autoevent_ballsnap.
- **Frame_Lancer** : frame de l'événement pass_forward, sinon autoevent_passforward.
- **Route** : trajectoire d'un WR de Frame_Snap à Frame_Lancer incluses, en coordonnées normalisées (attaque vers la droite).
- **Ligne_De_Melee** : x du ballon (team = "football") à Frame_Snap.
- **Enjeu_Eleve** : action dont indice_enjeu ≥ seuil retenu ; les autres actions sont en enjeu normal.
- **WR_Qualifie** : WR avec ≥ 30 Routes en Enjeu_Eleve et ≥ 30 Routes en enjeu normal.
- **Habitude** : valeur de choix (type_route ou vs_marqueur) la plus fréquente d'un WR en enjeu normal.
- **Taux_Habitude** : part des Routes d'un WR égales à son Habitude, calculée séparément en enjeu normal et en Enjeu_Eleve.
- **Score_Lisibilite** : (Taux_Habitude élevé − Taux_Habitude normal) − moyenne de cette variation sur les WR_Qualifie ; positif = plus lisible quand l'enjeu monte.
- **Mode_Echantillon** : exécution de l'Extracteur_Routes sur les 10 premiers fichiers de tracking (ordre alphabétique).

## Règles de référence type_route V3

Règles validées par l'utilisateur, appliquées dans l'ordre (première règle vérifiée retenue), distances en yards, vitesse en yd/s :

| Ordre | type_route | Règle |
|---|---|---|
| 1 | Flat/Screen | prof_max < 3 |
| 2 | Retour (hitch/curl/comeback) | (recul ≥ 1 ou vitesse_au_lancer < 2,5) et 3 ≤ prof_max ≤ 18 |
| 3 | Slant | 3 ≤ prof_max ≤ 8 et lateral ≤ −2 |
| 4 | Out | 3 ≤ prof_max ≤ 15 et lateral ≥ 2 |
| 5 | In/Dig | 8 ≤ prof_max ≤ 18 et lateral ≤ −2 |
| 6 | Go | prof_max ≥ 10 et abs(lateral) < 2 |
| 7 | Post | prof_max ≥ 15 et lateral ≤ −2 |
| 8 | Corner | prof_max ≥ 15 et lateral ≥ 2 |
| 9 | Autre | le reste |

Répartition de référence en Mode_Echantillon : Out 25,2 %, Autre 14,5 %, Go 12,6 %, In/Dig 11,4 %, Slant 10,7 %, Retour 10,1 %, Flat/Screen 8,2 %, Corner 5,0 %, Post 2,3 %.

## Requirements

### Exigence 1 : Socle commun [P0]

**Récit utilisateur :** En tant qu'équipe du hackathon, je veux des scripts simples et autonomes, afin de livrer un résultat reproductible avant le gel du code à 15h15.

#### Critères d'acceptation

1. THE Pipeline SHALL fournir à la racine du dépôt 01_build_plays.py, 02_extract_routes.py, 03_habitude.py, 04_model.py (seulement si l'exigence 10 [P2] est réalisée) et 05_viz.py. Chaque script SHALL se lancer seul par `py <script>` depuis la racine, sans argument obligatoire (`--echantillon` reste optionnel) et sans importer explore.py ni un autre script du Pipeline.
2. THE Pipeline SHALL écrire tous les fichiers produits dans outputs/ à la racine (dossier créé s'il est absent) et nulle part ailleurs, en écrasant à chaque exécution les fichiers de même nom.
3. THE Pipeline SHALL recopier depuis explore.py, sans modifier explore.py, le chargement des CSV de data/ et la conversion de gameClock « MM:SS » en secondes restantes dans le quart-temps (« 2:00 » → 120 ; valeur non convertible → valeur manquante).
4. THE Pipeline SHALL importer uniquement la bibliothèque standard Python, pandas, numpy, matplotlib, scikit-learn et scipy. Chaque script SHALL commencer par une docstring en français (rôle, entrées, sorties) et contenir au moins un commentaire en français par fonction.
5. THE Pipeline SHALL afficher dans la console de chaque script :
   - le chemin et le nombre de lignes de chaque CSV écrit ;
   - le chemin de chaque PNG écrit ;
   - pour chaque fait mesuré que le script recalcule, la valeur obtenue, la valeur de référence et l'écart.
   Le tout sans framework de tests : aucun import de unittest ou pytest, aucun dossier de tests.
6. THE Pipeline SHALL employer « quand l'enjeu monte » (casse ignorée) dans le titre de chaque PNG nuage_habitude* et classement*, dans au moins une ligne de console de 03_habitude.py et dans le README. THE Pipeline SHALL avoir 0 occurrence de « sous pression » (recherche insensible à la casse) dans les fichiers .py et README.md.
7. THE Pipeline SHALL inclure à la racine un .gitignore avec lequel git ignore data/ et tout son contenu, sans ignorer aucun fichier .png de outputs/.
8. WHEN un script est lancé par `py <script>` alors que tous ses fichiers d'entrée existent dans data/ ou outputs/, THE Pipeline SHALL terminer le script avec le code de sortie 0, sauf pour l'arrêt prévu par l'exigence 4, critère 6.
9. IF un fichier d'entrée d'un script est absent de data/ ou outputs/, THEN THE Pipeline SHALL afficher le chemin du fichier manquant et s'arrêter avec un code de sortie non nul, sans créer ni modifier de fichier dans outputs/.

### Exigence 2 : Indice d'enjeu par action [P0]

**Récit utilisateur :** En tant qu'analyste, je veux un indice d'enjeu calculé avant le snap, afin de séparer les actions à enjeu normal des actions à enjeu élevé.

#### Critères d'acceptation

1. WHEN 01_build_plays.py est lancé, THE Script_Enjeu SHALL écrire outputs/plays_stakes.csv avec 8 557 lignes, une par (gameId, playId) de plays.csv sans doublon, et les colonnes gameId, playId, down, yardsToGo, quarter, sec_restantes (gameClock converti en secondes restantes dans le quart-temps, de 0 à 900), yards_to_goal, ecart_score, indice_enjeu, enjeu_eleve (vrai si indice_enjeu ≥ seuil retenu au critère 7, faux sinon).
2. THE Script_Enjeu SHALL calculer indice_enjeu, entier de 0 à 8, avec uniquement des informations d'avant le snap (down, yardsToGo, quarter, sec_restantes, ecart_score, yards_to_goal ; aucune colonne de résultat comme passResult ou playResult) : +1 si down = 3, +2 si down = 4 ; +1 si yardsToGo ≥ 7 ; +1 si quarter ≥ 4 ; +2 si |ecart_score| ≤ 8 ; +1 si sec_restantes ≤ 120 et quarter ∈ {2, 4, 5} ; +1 si yards_to_goal ≤ 20 (la prolongation, quarter = 5, compte comme un 4e quart-temps ; une condition portant sur une valeur manquante rapporte 0 point).
3. THE Script_Enjeu SHALL calculer ecart_score du point de vue de possessionTeam : preSnapHomeScore − preSnapVisitorScore si possessionTeam = homeTeamAbbr (games.csv), l'opposé sinon (positif = l'équipe en possession mène).
4. THE Script_Enjeu SHALL calculer yards_to_goal = 100 − yardlineNumber si yardlineSide = possessionTeam, et yards_to_goal = yardlineNumber sinon (valeurs de 1 à 99).
5. IF yardlineSide est vide (ballon sur la ligne des 50), THEN THE Script_Enjeu SHALL fixer yards_to_goal à 50 et afficher le nombre d'actions concernées (attendu : 125).
6. WHEN indice_enjeu est calculé, THE Script_Enjeu SHALL afficher, pour chaque seuil candidat ≥ 3, ≥ 4 et ≥ 5, la part d'actions à enjeu élevé parmi les 7 565 actions avec passResult ∈ {C, I, IN} et le nombre de WR_Qualifie, en comptant une ligne par (gameId, playId, nflId) de pffScoutingData.csv avec pff_role = "Pass Route" et officialPosition = "WR" sur ces actions (attendu : ≥ 3 : 68,1 % / 87 ; ≥ 4 : 29,1 % / 83 ; ≥ 5 : 7,7 % / 5).
7. THE Script_Enjeu SHALL retenir et afficher, parmi les seuils candidats gardant ≥ 80 WR_Qualifie, celui dont la part d'actions à enjeu élevé est la plus proche de 35 %, le seuil le plus élevé l'emportant en cas d'égalité (attendu : ≥ 4, 29,1 %, 83 WR).
8. WHEN indice_enjeu est calculé, THE Script_Enjeu SHALL afficher l'effectif de chaque valeur de indice_enjeu sur les 8 557 actions et son écart à la référence {0 : 106, 1 : 1 045, 2 : 1 572, 3 : 3 298, 4 : 1 867, 5 : 566, 6 : 83, 7 : 19, 8 : 1} (écart attendu : 0 pour chaque valeur).

### Exigence 3 : Extraction des routes des WR [P0]

**Récit utilisateur :** En tant qu'analyste, je veux une ligne de mesures par Route, afin de classer chaque Route sans relire le tracking.

#### Critères d'acceptation

1. WHEN 02_extract_routes.py est lancé, THE Extracteur_Routes SHALL lire les 122 fichiers de tracking un par un et garder seulement les lignes du ballon, repérées par team = "football" (son nflId est vide), et celles des WR, repérées par les (gameId, playId, nflId) de pffScoutingData.csv avec pff_role = "Pass Route" et officialPosition = "WR" dans players.csv.
2. THE Extracteur_Routes SHALL prendre pour Frame_Snap la première frame portant ball_snap, sinon la première portant autoevent_ballsnap, et pour Frame_Lancer la première frame portant pass_forward, sinon la première portant autoevent_passforward ; l'événement manuel est retenu même quand l'événement auto existe aussi, quel que soit l'écart entre les deux.
3. IF une action n'a pas de Frame_Snap, n'a pas de Frame_Lancer ou a Frame_Lancer ≤ Frame_Snap, THEN THE Extracteur_Routes SHALL exclure l'action (aucune Route écrite) et afficher le nombre d'actions exclues par motif, chaque motif compté indépendamment (attendu en Mode_Echantillon : 3 sans Frame_Snap, 69 sans Frame_Lancer, 0 avec Frame_Lancer ≤ Frame_Snap).
4. IF un WR n'a pas de ligne de tracking à Frame_Snap ou à Frame_Lancer, THEN THE Extracteur_Routes SHALL exclure cette Route seulement, garder les autres Routes de l'action et afficher le nombre de Routes exclues pour ce motif.
5. IF playDirection = "left" pour une action, THEN THE Extracteur_Routes SHALL remplacer x par 120 − x et y par 53,3 − y sur toutes les lignes de l'action (WR et ballon), avant tout calcul de profondeur ou de lateral.
6. THE Extracteur_Routes SHALL calculer, en yards et sur les frames de Frame_Snap à Frame_Lancer incluses : profondeur = x du WR − Ligne_De_Melee (négative quand le WR est derrière la ligne), prof_max = maximum de profondeur, prof_au_lancer = profondeur à Frame_Lancer, recul = prof_max − prof_au_lancer (toujours ≥ 0) et vitesse_au_lancer = colonne s du WR à Frame_Lancer (yd/s).
7. THE Extracteur_Routes SHALL calculer lateral = côté × (y du WR à Frame_Lancer − y du WR à Frame_Snap), où côté = +1 si y du WR ≥ y du ballon à Frame_Snap et côté = −1 sinon ; lateral > 0 signifie un déplacement vers l'extérieur.
8. THE Extracteur_Routes SHALL écrire outputs/routes.csv avec exactement une ligne par Route retenue, sans doublon de (gameId, playId, nflId), et les colonnes gameId, playId, nflId, prof_max, prof_au_lancer, recul, lateral, vitesse_au_lancer, type_route.
9. WHEN le Mode_Echantillon se termine, THE Extracteur_Routes SHALL afficher le nombre d'actions dont la frame vient d'un événement auto (attendu : 0 pour Frame_Snap, 8 pour Frame_Lancer), la médiane, le minimum et le maximum de Frame_Lancer − Frame_Snap sur les actions retenues (attendu : 26, 13 et 98 frames) et la médiane de la profondeur des WR à Frame_Snap (attendu : −0,85 yd, écart ≤ 0,2 yd).
10. WHEN les 122 fichiers sont traités, THE Extracteur_Routes SHALL afficher le nombre de Routes (attendu entre 19 356 et 21 392, soit 20 374 ± 5 %), le nombre de WR distincts (attendu entre 199 et 219, soit 209 ± 5 %) et la durée totale d'exécution en secondes (attendu < 120 s).

### Exigence 4 : Type de route V3 et validation sur 10 matchs [P0]

**Récit utilisateur :** En tant qu'analyste, je veux un type de route compréhensible et validé visuellement, afin de ne pas bâtir la métrique sur une classification fausse.

#### Critères d'acceptation

1. THE Extracteur_Routes SHALL attribuer à chaque Route exactement un des 9 type_route : le premier dont la règle est vérifiée, dans l'ordre de la section « Règles de référence type_route V3 ». Une comparaison qui porte sur une mesure manquante compte comme fausse.
2. WHERE l'option `--echantillon` est passée en ligne de commande, THE Extracteur_Routes SHALL fonctionner en Mode_Echantillon et afficher le nombre total de Routes de l'échantillon ainsi que la part de chacun des 9 type_route en %, arrondie à 0,1 (types à 0 % compris).
3. WHERE le Mode_Echantillon est actif, THE Extracteur_Routes SHALL écrire outputs/grille_routes.png avec 9 vignettes, une par type_route dans l'ordre de la table V3. Chaque vignette contient 5 Routes du type, tirées sans remise avec la graine fixe 42 et tracées de Frame_Snap à Frame_Lancer. En abscisse : la position latérale depuis le départ, positive vers l'extérieur (à droite). En ordonnée : la profondeur. Chaque vignette porte une ligne horizontale à profondeur 0 (Ligne_De_Melee), utilise les mêmes échelles d'axes que les autres vignettes et a pour titre le type_route, son nombre de Routes et sa part en %.
4. WHERE le Mode_Echantillon est actif, IF un type_route compte moins de 5 Routes, THEN THE Extracteur_Routes SHALL dessiner toutes ses Routes et indiquer dans le titre de la vignette le nombre de Routes dessinées. S'il en compte 0, la vignette reste vide avec la mention « aucune Route ».
5. WHEN la répartition du Mode_Echantillon est affichée, THE Extracteur_Routes SHALL afficher pour chaque type_route l'écart signé en points (part mesurée − part de référence, arrondi à 0,1). Chaque type dont l'écart en valeur absolue dépasse 2 points est marqué « ÉCART > 2 pts », sans que ce seul marquage arrête l'exécution.
6. IF la part de « Autre » dépasse 20,0 % en Mode_Echantillon, THEN THE Extracteur_Routes SHALL écrire d'abord outputs/grille_routes.png, puis afficher « STOP : valider les règles type_route avant les 122 matchs » et s'arrêter avec un code de sortie non nul.

### Exigence 5 : Score de lisibilité quand l'enjeu monte [P0]

**Récit utilisateur :** En tant que coordinateur défensif, je veux savoir quels WR s'accrochent à leur habitude quand l'enjeu monte, afin de préparer ma défense pour ces situations.

#### Critères d'acceptation

1. THE Calculateur_Habitude SHALL fournir une fonction générique qui prend un tableau (nflId, gameId, playId, choix, enjeu_eleve booléen) et renvoie une ligne par WR_Qualifie.
2. THE Calculateur_Habitude SHALL calculer pour chaque WR_Qualifie : habitude (valeur de choix la plus fréquente parmi ses Routes en enjeu normal ; en cas d'ex æquo, la première dans l'ordre alphabétique croissant), taux_habitude_normal et taux_habitude_eleve (proportions entre 0 et 1), variation = taux_habitude_eleve − taux_habitude_normal et score_lisibilite_enjeu = variation − moyenne des variations des WR_Qualifie.
3. IF moins de 60 WR sont qualifiés à 30/30, THEN THE Calculateur_Habitude SHALL abaisser le minimum à 20/20 pour tous les WR et afficher le minimum utilisé.
4. THE Calculateur_Habitude SHALL calculer p_value par un test de permutation propre à chaque WR_Qualifie : 1 000 tirages qui mélangent les étiquettes enjeu_eleve entre ses Routes (n_normal et n_eleve conservés), habitude recalculée à chaque tirage sur l'échantillon normal permuté avec la même règle d'ex æquo, graine fixe 42 ; avec m = moyenne des 1 000 variations permutées du WR, k = nombre de tirages où |variation permutée − m| ≥ |variation observée − m|, et p_value bilatérale = (k + 1) / 1 001. L'habitude étant le choix le plus fréquent dans l'échantillon normal, taux_habitude_normal est biaisé vers le haut et la variation brute est en moyenne négative par construction : ce test, qui compare la variation du WR à sa propre distribution permutée, et le centrage du score corrigent ce biais.
5. THE Calculateur_Habitude SHALL marquer significatif = vrai si p_value < 0,05 (seuil non corrigé, décision de l'équipe), faux sinon, et garder en colonne q_value la correction de Benjamini-Hochberg sur l'ensemble des WR_Qualifie d'un même choix, en affichant le nombre de WR à q_value < 0,10 et le nombre de faux positifs attendus (0,05 × nombre de WR_Qualifie).
6. WHEN 03_habitude.py est lancé, THE Calculateur_Habitude SHALL appliquer la fonction avec choix = type_route et écrire outputs/score_wr_type_route.csv (une ligne par WR_Qualifie, displayName issu de players.csv ; colonnes nflId, displayName, n_normal, n_eleve, habitude, taux_habitude_normal, taux_habitude_eleve, variation, score_lisibilite_enjeu, p_value, q_value, significatif).
7. WHEN le score est calculé, THE Calculateur_Habitude SHALL afficher le minimum de Routes utilisé, le nombre de WR_Qualifie (attendu 83, écart ≤ 5 %), la moyenne des variations brutes (attendue négative), la moyenne des scores (|moyenne| ≤ 10⁻⁹), le nombre de WR significatifs, et les 5 scores les plus hauts et les 5 plus bas avec displayName et q_value.
8. WHEN 03_habitude.py est relancé sur les mêmes entrées, THE Calculateur_Habitude SHALL produire des p_value identiques.
9. WHEN le test de permutation d'un choix se termine, THE Calculateur_Habitude SHALL afficher sa durée d'exécution, inférieure à 2 minutes pour 1 000 permutations par WR_Qualifie (83 attendus).

### Exigence 6 : Nuage et classement [P0]

**Récit utilisateur :** En tant que commentateur TV, je veux deux graphiques compris d'un coup d'œil, afin d'expliquer à l'antenne quels WR deviennent lisibles quand l'enjeu monte.

#### Critères d'acceptation

1. WHEN 05_viz.py est lancé, THE Visualiseur SHALL lire uniquement des fichiers de outputs/, construire les deux graphiques à partir de outputs/score_wr_type_route.csv seul, écrire outputs/nuage_habitude.png et outputs/classement.png, puis afficher dans la console le chemin de chaque PNG écrit.
2. THE Visualiseur SHALL dessiner dans nuage_habitude.png un point par WR_Qualifie (x = taux_habitude_normal, y = taux_habitude_eleve, deux axes de 0 à 100 % à la même échelle), la diagonale y = x et le displayName de chaque WR significatif à côté de son point.
3. THE Visualiseur SHALL titrer nuage_habitude.png avec des chiffres calculés depuis score_wr_type_route.csv (jamais saisis à la main), au format « Quand l'enjeu monte : S+ WR deviennent plus lisibles, S− plus imprévisibles (sur N WR qualifiés, q < 0,10) », où N = nombre de WR_Qualifie, S+ = nombre de WR significatifs avec score_lisibilite_enjeu > 0 et S− = nombre de WR significatifs avec score_lisibilite_enjeu < 0.
4. THE Visualiseur SHALL dessiner dans classement.png des barres horizontales de score_lisibilite_enjeu, triées du score le plus haut (en haut) au plus bas : les 10 plus hauts en rouge (lisibles), les 10 plus bas en vert (imprévisibles). Chaque barre porte le displayName du WR, son nombre de Routes (n_normal + n_eleve) à côté de la barre et une étoile si significatif = vrai.
5. IF aucun WR n'est significatif, THEN THE Visualiseur SHALL quand même écrire les deux PNG, afficher dans nuage_habitude.png le displayName des 3 WR aux scores les plus hauts et des 3 WR aux scores les plus bas, mettre S+ = 0 et S− = 0 dans le titre, ne dessiner aucune étoile dans classement.png et afficher dans la console un message indiquant qu'aucun WR n'est significatif.
6. THE Visualiseur SHALL respecter pour chaque graphique les règles suivantes : des libellés d'axes en français avec leur unité (%), sans nom de colonne brut (aucun caractère « _ ») ; une légende des éléments dessinés (diagonale pour le nuage ; rouge = lisible quand l'enjeu monte, vert = imprévisible et étoile = significatif pour le classement) ; une police d'au moins 10 pt pour tout le texte ; une résolution d'au moins 150 dpi et une taille d'au moins 1 200 × 800 pixels.

### Exigence 7 : Fiche cas d'usage d'un joueur [P1]

**Récit utilisateur :** En tant que coordinateur défensif, je veux la fiche de tendance d'un WR, afin de voir concrètement comment ses routes changent quand l'enjeu monte.

#### Critères d'acceptation

1. WHEN les 122 fichiers sont traités, THE Extracteur_Routes SHALL écrire outputs/trajectoires.csv avec une ligne par Route et par frame de Frame_Snap à Frame_Lancer incluses (colonnes gameId, playId, nflId, frame_rel = frame − Frame_Snap, avance = x du WR − x du WR à Frame_Snap, lateral = déplacement latéral depuis la position du WR à Frame_Snap, positif vers l'extérieur comme à l'exigence 3 ; avance et lateral arrondis à 0,1 yd), puis afficher son nombre de lignes (estimation ≈ 550 000), son nombre de Routes distinctes (égal au nombre de lignes de routes.csv) et sa taille (attendu < 50 Mo).
2. WHEN 05_viz.py est lancé, THE Visualiseur SHALL choisir dans outputs/score_wr_type_route.csv le WR avec significatif = vrai au score_lisibilite_enjeu le plus élevé (égalité départagée par le plus petit nflId), puis afficher son displayName et le motif du choix (significatif ou repli).
3. IF aucun WR n'a significatif = vrai, THEN THE Visualiseur SHALL choisir le WR au score_lisibilite_enjeu le plus élevé parmi les WR_Qualifie dont n_normal + n_eleve est strictement supérieur à la médiane de n_normal + n_eleve des WR_Qualifie.
4. THE Visualiseur SHALL écrire outputs/fiche_<nom>.png, où <nom> est le displayName sans accents, espaces remplacés par « _ », puis tout caractère autre que lettre ASCII, chiffre ou « _ » supprimé (ex. « Amon-Ra St. Brown » → fiche_AmonRa_St_Brown.png), avec un panneau de barres côte à côte donnant, pour les 9 type_route dans l'ordre des règles V3, la part en % des Routes du WR en enjeu normal et en Enjeu_Eleve (total de 100 % par niveau).
5. THE Visualiseur SHALL dessiner sur la fiche deux cartes de trajectoires snap → lancer (enjeu normal, Enjeu_Eleve), chacune avec min(30, n) Routes du WR tirées au hasard avec la graine 42 (n = nombre de Routes du WR à ce niveau d'enjeu), chaque Route partant de l'origine (0, 0) = position du WR à Frame_Snap, lateral en abscisse (extérieur toujours à droite), avance en ordonnée et mêmes bornes d'axes sur les deux cartes.
6. THE Visualiseur SHALL indiquer dans le titre de la fiche le displayName du WR, n_normal, n_eleve et score_lisibilite_enjeu arrondi à 2 décimales avec son signe.
7. THE Pipeline SHALL exclure outputs/trajectoires.csv via .gitignore, ce fichier étant régénéré par 02_extract_routes.py.

### Exigence 8 : Variante position par rapport au marqueur [P1]

**Récit utilisateur :** En tant que coordinateur défensif, je veux savoir si un WR vise plus souvent la même zone par rapport au marqueur de premier essai quand l'enjeu monte, afin d'ajuster la profondeur de ma couverture.

#### Critères d'acceptation

1. THE Extracteur_Routes SHALL ajouter à outputs/routes.csv la colonne vs_marqueur, calculée à partir de prof_au_lancer (non arrondie) et de yardsToGo de plays.csv joint par (gameId, playId) : « avant » si prof_au_lancer < yardsToGo − 2, « au_marqueur » si yardsToGo − 2 ≤ prof_au_lancer ≤ yardsToGo + 2 (bornes incluses), « au_dela » si prof_au_lancer > yardsToGo + 2.
2. WHEN le Mode_Echantillon se termine, THE Extracteur_Routes SHALL afficher, pour chacune des 3 valeurs de vs_marqueur, sa part en % (1 décimale) et son écart en points à la référence (avant 34,8 %, au_marqueur 26,7 %, au_dela 38,6 %), avec un écart absolu attendu ≤ 2 points pour chaque valeur.
3. WHEN 03_habitude.py est lancé, THE Calculateur_Habitude SHALL appliquer la fonction de l'exigence 5 avec choix = vs_marqueur et les mêmes paramètres (seuil d'enjeu retenu, minimum de Routes utilisé, 1 000 permutations, graine 42, correction de Benjamini-Hochberg, q_value < 0,10), écrire outputs/score_wr_vs_marqueur.csv avec les 12 colonnes de score_wr_type_route.csv (habitude ∈ {avant, au_marqueur, au_dela}) et afficher les contrôles console du critère 7 de l'exigence 5.
4. WHEN 05_viz.py est lancé, THE Visualiseur SHALL écrire outputs/nuage_habitude_vs_marqueur.png et outputs/classement_vs_marqueur.png à partir de score_wr_vs_marqueur.csv selon les critères 2 à 4 de l'exigence 6, avec un titre qui contient « par rapport au marqueur ».
5. THE README SHALL préciser que vs_marqueur se mesure par rapport au marqueur de premier essai (yardsToGo) et non en profondeur absolue, et que yardsToGo ≥ 7 ajoutant +1 à indice_enjeu, les actions en Enjeu_Eleve ont plus souvent un marqueur lointain.

### Exigence 9 : README [P0]

**Récit utilisateur :** En tant que membre du jury, je veux un README autoportant, afin de comprendre le résultat et de le reproduire.

#### Critères d'acceptation

1. THE README SHALL commencer par un résumé de 3 à 5 phrases indiquant ce qui a été construit, le résultat clé chiffré (nombre de WR_Qualifie, nombre de WR significatifs même s'il vaut 0, nom et score_lisibilite_enjeu du WR au score le plus élevé, lus dans outputs/score_wr_type_route.csv) et qui l'utiliserait (coordinateur défensif, commentateur TV), en formulant l'effet par « quand l'enjeu monte ».
2. THE README SHALL intégrer par liens Markdown relatifs (outputs/<fichier>.png) chaque PNG présent dans outputs/ à la soumission, dont au minimum nuage_habitude.png et classement.png, chaque lien pointant vers un fichier existant du dépôt.
3. THE README SHALL définir l'indice d'enjeu (les 6 pondérations de l'exigence 2 et le seuil retenu affiché par 01_build_plays.py), le WR_Qualifie, le Taux_Habitude, le Score_Lisibilite (positif = plus lisible quand l'enjeu monte) et le critère significatif (q_value < 0,10 après Benjamini-Hochberg).
4. THE README SHALL lister les hypothèses et limites : seuils V3 des routes, pondérations de l'indice, Route mesurée au lancer (routes non cassées au lancer comptées en Go, Out ou Autre), taille des échantillons (minimum de Routes utilisé, 30/30 ou 20/20, tel qu'affiché par 03_habitude.py), significativité rare avec environ 30 à 60 Routes en Enjeu_Eleve par WR (un score non significatif décrit une tendance, pas une preuve), Out gonflé par les releases extérieures.
5. THE README SHALL contenir une section « Comment lancer » : télécharger les données depuis https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data dans data/ (games.csv, plays.csv, players.csv, pffScoutingData.csv et tracking/ avec 122 fichiers), exécuter `pip install pandas numpy matplotlib scikit-learn scipy`, puis lancer dans l'ordre `py 01_build_plays.py`, `py 02_extract_routes.py --echantillon` (validation), `py 02_extract_routes.py`, `py 03_habitude.py`, `py 04_model.py` et `py 05_viz.py`.
6. THE README SHALL citer chaque chiffre (seuil, part d'actions en Enjeu_Eleve, nombre de WR_Qualifie, nombre de WR significatifs, scores, q_value) tel que produit par les scripts dans outputs/ ou affiché dans la console, arrondi à 0,1 point pour les parts et à 2 décimales pour les scores, et non tiré des valeurs attendues de cette spec.

### Exigence 10 : Modèle prédictif bonus [P2]

**Récit utilisateur :** En tant qu'analyste, je veux confirmer la lisibilité avec un modèle d'avant le snap, afin de valider le score par une seconde méthode.

#### Critères d'acceptation

1. WHERE les étapes 1 à 4 sont terminées avant 15h00, WHEN 04_model.py est lancé, THE Modele_Bonus SHALL entraîner un HistGradientBoostingClassifier (graine fixe 42) qui prédit type_route sur toutes les Routes de outputs/routes.csv (nombre affiché, égal au nombre de lignes du fichier) à partir de 11 variables : down, yardsToGo, yards_to_goal, quarter, ecart_score, sec_restantes et indice_enjeu en numérique ; offenseFormation, personnelO, pff_positionLinedUp et nflId en catégories natives du modèle (nflId jamais traité comme un nombre), valeurs manquantes conservées sans retirer de Route.
2. THE Modele_Bonus SHALL produire pour chaque Route exactement un jeu de probabilités hors échantillon sur les 9 type_route, par GroupKFold à 5 plis sur gameId (aucun gameId à la fois dans l'entraînement et le test d'un même pli).
3. THE Modele_Bonus SHALL calculer, pour chaque WR_Qualifie (même seuil d'enjeu et même minimum de Routes que l'exigence 5) : proba_normal et proba_eleve = moyenne de la probabilité hors échantillon de sa vraie type_route sur ses Routes en enjeu normal et en Enjeu_Eleve, variation_modele = proba_eleve − proba_normal et score_modele = variation_modele − moyenne des variation_modele des WR_Qualifie (positif = plus prévisible quand l'enjeu monte).
4. THE Modele_Bonus SHALL entraîner le même modèle sans indice_enjeu (mêmes 10 autres variables, mêmes plis, même graine) et afficher dans la console, une ligne par modèle, la log-loss (3 décimales) et l'exactitude (en %, 1 décimale) calculées sur les probabilités hors échantillon de toutes les Routes.
5. THE Modele_Bonus SHALL écrire outputs/model_lisibilite.png : un point par WR_Qualifie (x = score_lisibilite_enjeu lu dans outputs/score_wr_type_route.csv, y = score_modele), les droites x = 0 et y = 0, le nom de chaque WR significatif et un titre qui énonce la corrélation de Spearman du critère 7, en respectant l'exigence 6, critère 6.
6. THE Modele_Bonus SHALL n'utiliser aucune variable hors des 11 du critère 1, en particulier aucune information d'après le snap : ni x, y, s ou autre colonne du tracking, ni prof_max, prof_au_lancer, recul, lateral, vitesse_au_lancer ou vs_marqueur, ni passResult, playResult, dropBackType, pff_playAction ou pff_passCoverage.
7. WHEN score_modele est calculé, THE Modele_Bonus SHALL afficher le nombre de WR_Qualifie (égal au nombre de lignes de outputs/score_wr_type_route.csv), la corrélation de Spearman entre score_modele et score_lisibilite_enjeu (2 décimales) et sa p_value.

### Exigence 11 : Cas d'usage avec une star (06_cas_usage.py) [P1]

**Récit utilisateur :** En tant que coordinateur défensif ou commentateur TV, je veux la fiche de tendance d'un WR connu, afin de raconter le résultat avec un joueur que tout le monde identifie.

Cette exigence remplace les critères 2 à 6 de l'exigence 7 : la fiche est produite par 06_cas_usage.py et non par 05_viz.py. Le critère 1 (trajectoires.csv) et le critère 7 (.gitignore) de l'exigence 7 restent valables.

#### Critères d'acceptation

1. THE Cas_Usage SHALL rechercher dans displayName de players.csv la liste de stars 2021 : Cooper Kupp, Davante Adams, Tyreek Hill, Justin Jefferson, Ja'Marr Chase, Deebo Samuel, CeeDee Lamb, Stefon Diggs, DK Metcalf, Mike Evans, Chris Godwin, Keenan Allen, A.J. Brown, Diontae Johnson, Tyler Lockett, Terry McLaurin, DJ Moore, Amari Cooper, Mike Williams, Hunter Renfrow, Marquise Brown, Jaylen Waddle, Adam Thielen, Brandin Cooks, et afficher les noms introuvables.
2. THE Cas_Usage SHALL afficher le tableau des stars qualifiées (WR_Qualifie de outputs/score_wr_type_route.csv) : nom, équipe (possessionTeam la plus fréquente sur ses Routes), n normal, n élevé, habitude, taux normal, taux élevé, score_lisibilite_enjeu, q_value, et l'écrire dans outputs/stars_qualifiees.csv.
3. THE Cas_Usage SHALL retenir comme star principale la star significative au score le plus élevé, sinon la star qualifiée au score le plus élevé, sinon (aucune star qualifiée) le WR_Qualifie au score le plus élevé, et afficher le motif du choix.
4. THE Cas_Usage SHALL écrire outputs/fiche_<nom>.png (règle de nom de l'exigence 7, critère 4) avec : (a) un en-tête nom, équipe, nombre de Routes, score et étoile si significatif ; (b) des barres côte à côte de la répartition des 9 type_route en enjeu normal et élevé ; (c) deux cartes de trajectoires sur fond de terrain (terrain.py s'il existe, sinon fond dessiné par matplotlib), enjeu normal / enjeu élevé, extérieur à droite ; (d) une phrase de conseil générée automatiquement.
5. THE Cas_Usage SHALL générer la phrase de conseil au format « Quand l'enjeu monte, <nom> court un <type dominant> dans X % des cas (contre Y % habituellement) → <conseil> », où le type dominant est le type_route le plus fréquent en enjeu élevé, X sa part en enjeu élevé et Y sa part en enjeu normal, avec le dictionnaire : Out/Corner → « jouer son côté extérieur » ; Slant/In/Dig/Post → « fermer l'intérieur » ; Go → « garder un safety profond sur lui » ; Retour → « ne pas reculer, attaquer le point de retour » ; Flat/Screen → « un linebacker prêt sur le flat » ; Autre → « rester en couverture de zone ».
6. WHERE le temps le permet, THE Cas_Usage SHALL produire une seconde fiche pour la star qualifiée au score le plus bas (la plus imprévisible quand l'enjeu monte), avec la même mise en page.
