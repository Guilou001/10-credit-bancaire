#set document(title: "Construire un modèle de crédit, puis vérifier ce qu'il mesure", author: "Guillaume Vaudescal")
#set page(
  paper: "a4",
  margin: (x: 2.2cm, y: 2.4cm),
  numbering: "1 / 1",
  footer: context [
    #set text(size: 8pt, fill: luma(90))
    #grid(columns: (1fr, auto), align: (left, right),
      [credit-lab-ca], [#counter(page).display("1 / 1", both: true)])
  ],
)
#set text(font: ("Helvetica", "Arial", "DejaVu Sans"), size: 10pt, lang: "fr")
#set par(justify: true, leading: 0.68em, spacing: 1.1em)
#set heading(numbering: none)
#show heading.where(level: 2): it => block(above: 1.6em, below: 0.8em, text(size: 13pt, it))
#show heading.where(level: 3): it => block(above: 1.2em, below: 0.6em, text(size: 11pt, it))
#show raw.where(block: true): it => block(
  fill: luma(246), inset: 8pt, radius: 3pt, width: 100%, text(size: 8.5pt, it))
#show raw.where(block: false): it => text(size: 9pt, fill: rgb("#1a3f66"), it)
#show quote.where(block: true): it => block(
  inset: (left: 10pt), stroke: (left: 1.5pt + luma(180)),
  text(style: "italic", fill: luma(45), it.body))
// la table NE DOIT PAS être enfermée dans un par() : Typst 0.15 la supprime alors
// entièrement, sans erreur. Le réglage se pose donc dans la portée du bloc.
#show table: it => block(above: 1.1em, below: 1.1em,
  [#set par(justify: false); #text(size: 8.8pt, it)])
#show figure: it => block(above: 1.4em, below: 1.4em, it)
#show figure.caption: it => text(size: 8.5pt, fill: luma(70), it)
#show link: it => text(fill: rgb("#0072B2"), it)

#align(center)[
  #block(width: 100%)[
    #text(size: 18pt, weight: "bold")[Construire un modèle de crédit, puis vérifier ce qu'il mesure]
    #v(0.6em)
    #text(size: 10pt, fill: luma(70))[Guillaume Vaudescal · 2026-09-04 · #link("https://github.com/Guilou001/10-credit-bancaire")[Guilou001/10-credit-bancaire]]
  ]
]
#v(1.2em)
#line(length: 100%, stroke: 0.6pt + luma(190))
#v(0.8em)

Une banque doit estimer la probabilité qu'un emprunteur ne rembourse pas son prêt. Cette probabilité sert ensuite à calculer une provision comptable, un besoin de capital et une décision de crédit. Toutefois, de bons indicateurs de classement ne suffisent pas à prouver que le modèle retrouve correctement le risque.

Le présent projet construit d'abord un portefeuille simulé dont les paramètres sont connus. Trois moteurs de probabilité de défaut doivent retrouver ces paramètres avant d'être utilisés dans des exercices bancaires. Le dépôt relie ensuite cette vérification à une provision selon IFRS 9, à la formule de capital du BSIF et à un dossier de crédit sur Enbridge.

*Résultat principal.* Sur 8 000 prêts et 381 686 observations mensuelles, le modèle retrouve les trois paramètres du simulateur à moins de 0,07 près. Son aire sous la courbe atteint 0,767 et l'écart moyen de calibration vaut 0,18 point de pourcentage. De plus, la provision pondérée par trois scénarios atteint 13,18 millions de dollars, contre 13,10 millions pour le seul scénario central. Cet écart mesure l'effet de la convexité plutôt que l'effet d'un scénario moyen différent.

Afin de suivre le projet de bout en bout, nous présenterons d'abord les prêts simulés, les données publiques et leurs limites. Dans un deuxième temps, nous expliquerons les trois moteurs et la manière dont ils sont contrôlés. Ensuite, nous calculerons la provision, le capital réglementaire et les indicateurs du dossier Enbridge. Enfin, nous présenterons les résultats, le classeur Excel et la procédure de reproduction.

Le même contenu en PDF : #link("rapport/rapport.pdf")[rapport/rapport.pdf].

== Résumé en anglais

_English summary._ Credit risk end to end, with a verification twist: three PD engines (WoE scorecard, Shumway discrete-time hazard, Vasicek point-in-time) tested on a synthetic loan-month panel with KNOWN parameters that the hazard model provably recovers; IFRS 9 ECL with weighted scenarios and staging (weighted ECL exceeds the central scenario, convexity measured); OSFI-floored IRB mortgage capital verified against a hand computation; real Canadian big-six loan-loss provisions (Bank of Canada Valet, peak 1.42 % in 2020Q2, negative in 2021); and the deliverable every commercial-credit posting asks for: a full Excel credit file on Enbridge (spreading, ratios, live-formula projections, weighted scorecard, covenants) with a bilingual memo explaining why a generic rubric yields internal B where agencies assign BBB. Freddie Mac loan-level data requires registration and is declared as a manual deposit, not silently skipped.

== 1. La question en détail

Un modèle de crédit peut avoir de bons indicateurs et être faux : comment PROUVER qu'un moteur de PD mesure ce qu'il prétend ? La réponse du dépôt : le faire tourner sur un monde où la vérité est connue. Un portefeuille synthétique est généré par un modèle de hasard dont on fixe les paramètres, puis chaque moteur est jugé sur sa capacité à les retrouver. En mots simples : avant de croire un modèle sur des données réelles, on vérifie qu'il retrouve la recette d'un monde qu'on a fabriqué. Ensuite viennent les trois usages bancaires : provisionner (IFRS 9), capitaliser (Bâle/OSFI), et décider d'un crédit (le dossier Enbridge).

== 2. D'où vient le projet, et ce qu'il apporte

Les briques sont canoniques : la carte de score à poids de la preuve (le standard bancaire), le hasard en temps discret de Shumway (2001), le modèle à un facteur de Vasicek (2002) qui fonde à la fois le passage au point du cycle et la formule de capital de Bâle (BCBS, 2005), l'ECL d'IFRS 9 (BCBS d350, 2015), et les planchers du chapitre 5 de la ligne directrice sur les normes de fonds propres de l'OSFI (corrélation hypothécaire 0,15, PD plancher 0,05 %, LGD plancher 10 %, rapportés). Ce que ce dépôt apporte :

- *La vérification sur des paramètres connus d'avance* : le simulateur (défaut ET remboursement anticipé en

risque concurrent) est publié avec ses paramètres, et le test exige que le moteur les retrouve.

- *La convexité rendue visible* : l'ECL pondérée par scénarios dépasse l'ECL du scénario

central, sur les mêmes prêts, par la convexité de la PD dans le cycle et l'asymétrie déclarée des scénarios ; c'est l'argument central d'IFRS 9 et il est mesuré, pas affirmé.

- *Le miroir réel* : les provisions des grandes banques canadiennes (Valet, série

FVI\_PCL\_RATIO\_SIB) donnent l'échelle du vrai cycle du crédit, pic à 1,42 % au T2 2020 et reprises NÉGATIVES en 2021.

- *Le volet obligatoire du métier* : le dossier de crédit Excel (étalement, ratios, projection à

formules vivantes, grille de cotation, covenants) sur une vraie société du TSX.

== 3. Les données

#table(
  columns: 3,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Source*],
    [*Contenu*],
    [*Statut et accès*],
    [Simulateur du dépôt],
    [8 000 prêts, 72 mois, hasard logistique (constante −6,2 ; score −1,1 ; cycle 0,9), remboursement anticipé 0,8 %/mois],
    [paramètres connus d'avance, graine fixée],
    [SEC, companyfacts (CIK 895728)],
    [Enbridge, exercices 2011-2025 en CAD (revenus, EBITDA, dette, intérêts, flux ; la source remonte à 2010, l'exercice incomplet est écarté, coupe déclarée)],
    [mesuré ; #raw("clab fetch"), jamais commité],
    [Banque du Canada, Valet],
    [FVI\_PCL\_RATIO\_SIB : provisions pour pertes / encours, grandes banques, 2018-2026 trimestriel],
    [mesuré (rapporté par la BdC) ; #raw("clab fetch")],
    [Freddie Mac, échantillon prêt par prêt],
    [50 000 prêts par millésime, 1999-2026],
    [inscription gratuite non scriptable : DÉPÔT MANUEL déclaré, le laboratoire tourne sans lui sur le synthétique],
)

== 4. La méthode, pas à pas

+ *Simuler la vérité* : chaque mois, chaque prêt vivant fait défaut avec un hasard logistique (fonction de son score à l'octroi et du cycle), ou rembourse par anticipation (risque concurrent qui censure la trajectoire, le piège classique des données de prêts).
+ *Trois moteurs de PD.* La carte de score : le score est découpé en classes, chaque classe reçoit son poids de la preuve (WoE, le logarithme du rapport bons/mauvais de la classe relatif au portefeuille), une logistique prédit le défaut à 12 mois. Le hasard de Shumway : une logistique sur TOUTES les lignes prêt-mois, cycle compris ; la PD à 12 mois se compose mois par mois. Vasicek : la PD moyenne de long terme (TTC) se déplace avec le facteur commun du moment (PIT) ; la moyenne des PIT sur le cycle redonne la TTC, testé.
+ *Provisionner (IFRS 9)* : stade 1 (provision 12 mois) ou stade 2 (provision à VIE) selon que la PD a plus que doublé depuis l'octroi (seuil déclaré, comparé à échelle TTC contre TTC) ; trois scénarios macroéconomiques pondérés 25/50/25 ; l'ECL finale est la moyenne pondérée.
+ *Capitaliser (OSFI)* : la formule IRB hypothécaire, corrélation 0,15, confiance 99,9 %, planchers de PD et de LGD ; vérifiée contre un calcul à la main dans les tests.
+ *Décider (le dossier)* : étalement d'Enbridge, ratios de crédit (levier, couverture, DSCR, FFO/dette), projection à trois ans dont les hypothèses sont des cellules modifiables, grille de cotation pondérée, clauses proposées, mémo bilingue.

== 5. Les résultats (mesurés, sources dans results/tables/)

#table(
  columns: 2,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Ce qui est vérifié*],
    [*Chiffre*],
    [Hasard : constante (vrai −6,20)],
    [estimé −6,13 (#raw("hasard_verite_vs_estime.csv"))],
    [Hasard : coefficient du score (vrai −1,10)],
    [estimé −1,05],
    [Hasard : coefficient du cycle (vrai 0,90)],
    [estimé 0,85],
    [Pouvoir de classement du score : aire, Gini, écart de Kolmogorov-Smirnov],
    [0,767 ; 0,534 ; 0,404 (#raw("discrimination.csv"))],
    [Calibration : écart moyen entre annoncé et réalisé],
    [+0,18 point, 0 tranche sur 10 hors du hasard (#raw("calibration.csv"))],
    [ECL par scénario (favorable / base / adverse)],
    [9,79 / 13,10 / 16,72 M\$ (#raw("ecl_scenarios.csv"))],
    [ECL pondérée contre centrale],
    [13,18 contre 13,10 M\$ : la convexité coûte 0,6 %],
    [Part du livre en stade 2 (construite : un tiers détérioré)],
    [33,2 %],
    [Capital IRB, PD 1 %, LGD 25 %],
    [K = 2,51 % de l'exposition (testé à la main)],
    [Provisions des grandes banques (Valet)],
    [pic 1,42 % au T2 2020, minimum −0,05 % en 2021],
    [Enbridge 2025 : levier, couverture, DSCR, FFO/dette],
    [6,28 x ; 3,31 x ; 1,40 x ; 11,75 %],
    [Note interne d'Enbridge (grille déclarée)],
    [2,40 sur 5, lettre B ; les agences : catégorie BBB (rapporté)],
)

Comment lire ce tableau, en trois constats. D'abord, la vérification sur des paramètres connus d'avance fonctionne : les trois paramètres sont retrouvés à moins de 0,07 près, sur un panel où 20,4 % des prêts font défaut et où le remboursement anticipé censure les autres ; c'est la preuve que le moteur mesure bien le hasard et pas un artefact. Ensuite, la pondération de scénarios n'est pas un rituel : sur les mêmes prêts, elle ajoute 0,6 % à la provision du seul scénario central, par la convexité de la PD dans le cycle et par l'asymétrie déclarée des scénarios (états du cycle −1,0 ; 0 ; +1,5, poids 25/50/25) ; l'écart grandit avec le poids des queues. Enfin, l'écart entre le B interne d'Enbridge et le BBB des agences n'est pas une erreur de calcul : c'est la limite structurelle d'une grille de ratios, aveugle à la nature contractuelle des flux d'un pipeline réglementé, et le mémo la déclare au lieu de la maquiller.

=== Le score classe-t-il, et ses probabilités tombent-elles juste

Ce sont deux questions différentes, et un modèle peut réussir l'une et manquer l'autre. La première demande si le score range les emprunteurs dans le bon ordre. La seconde demande si les probabilités qu'il annonce sont du bon niveau : un score peut classer parfaitement et annoncer 2 % de défauts là où il y en a 6 %.

#figure(image("../results/figures/discrimination.png", width: 100%), caption: [Le pouvoir de classement du score et la justesse de ses probabilités])

Comment lire cette figure : à gauche, la part des défaillants qu'on attrape en fonction de la part de sains qu'on rejette. Plus la courbe monte vite, mieux le score classe. L'aire sous cette courbe vaut *0,767*, ce qui veut dire que sur deux emprunteurs tirés au hasard, l'un défaillant et l'autre non, le score met le défaillant devant dans 76,7 % des cas. À droite, chaque point est une tranche de probabilité annoncée, et sa position verticale est ce qui est réellement arrivé ; les barres sont l'incertitude due au nombre d'emprunteurs de la tranche.

Comment lire ces deux nombres, en trois constats. Le premier est que l'aire de 0,767 est *exactement celle qu'atteindrait quelqu'un qui connaîtrait la vraie loi des défauts*, à quinze décimales. Ce n'est pas un exploit de l'estimation et il ne faut pas le présenter comme tel : le portefeuille construit n'a qu'une seule variable d'emprunteur, et tout classement croissant de cette variable donne le même ordre. Il n'y avait rien à gagner ni à perdre sur le classement. Le deuxième est que c'est donc la *calibration* qui porte le vrai résultat : les coefficients estimés auraient pu être faux, et les probabilités annoncées auraient alors été décalées. Elles ne le sont pas, l'écart moyen valant *+0,18 point* et aucune des dix tranches ne sortant du hasard de l'échantillon. Le troisième est que ce compte de tranches se lit avec la taille de l'échantillon en tête : sur vingt mille emprunteurs par tranche, l'incertitude tombe à 0,07 point et un écart de 0,15 point, sans intérêt pour un service de crédit, sortirait déjà du hasard.

#figure(image("../results/figures/pcl_grandes_banques.png", width: 100%), caption: [Provisions des grandes banques])

Comment lire cette figure : la part des encours de prêts que les six grandes banques canadiennes provisionnent chaque trimestre (Valet, mesuré) ; le pic de 1,42 % au T2 2020 est du provisionnement IFRS 9 par anticipation, et la descente sous ZÉRO en 2021 est la reprise de ces provisions quand la catastrophe attendue n'est pas venue : le mécanisme des scénarios pondérés, en vrai et en une courbe.

#figure(image("../results/figures/capital_irb.png", width: 100%), caption: [Capital IRB])

Comment lire cette figure : l'exigence de capital K en pourcent de l'exposition, le long de la PD en échelle logarithmique ; la courbe pleine applique les planchers de l'OSFI, qui relèvent le bas de la courbe (aucun prêt, si beau soit son score, ne porte moins de capital que PD 0,05 % et LGD 10 % ne l'exigent).

#figure(image("../results/figures/ecl_scenarios.png", width: 100%), caption: [ECL par scénarios])

Comment lire cette figure : l'ECL du portefeuille synthétique sous chacun des trois scénarios, et la ligne pointillée de l'ECL pondérée ; elle est AU-DESSUS de la barre du scénario de base parce que le scénario adverse (état du cycle +1,5) fait plus de dégâts que le favorable (−1,0) n'apporte de soulagement, la PD étant convexe dans le cycle : l'argument des scénarios pondérés, visible à l'œil nu.

#figure(image("../results/figures/enbridge_ratios.png", width: 100%), caption: [Ratios de crédit d'Enbridge])

Comment lire cette figure : les barres sont le levier (dette long terme sur EBITDA), la ligne la couverture des intérêts, depuis 2017 (la dette SEC d'Enbridge commence là ; le pic de 2017 est l'exercice de la fusion Spectra, EBITDA en année partielle). Le levier vit autour de 6 x et la couverture a glissé de 4,4 x en 2019 à 3,3 x en 2025 avec la hausse des taux : c'est la ligne à surveiller du dossier.

Le dossier complet : #link("reports/dossier_credit_enbridge.xlsx")[classeur Excel] (étalement, projection à formules, cotation, covenants) et #link("reports/memo_credit_enbridge.md")[mémo bilingue].

== 6. Reproduire

#raw("uv sync --locked --all-extras     # environnement verrouillé (Python 3.12, scikit-learn, openpyxl)\nuv run pytest                     # 9 tests : vérité retrouvée, IRB à la main, ECL, stades (sans réseau)\nuv run clab fetch                 # Enbridge (SEC) + provisions Valet ; Freddie Mac : dépôt manuel\nuv run clab lab                   # le laboratoire synthétique : PD, ECL, courbe IRB (quelques secondes)\nuv run clab mirror                # la figure des provisions réelles\nuv run clab credit                # le dossier Enbridge : tables, figure, classeur Excel", block: true, lang: "bash")

== 7. Limites, avec leur statut

#table(
  columns: 2,
  stroke: (x, y) => if y == 0 { (bottom: 0.6pt) } else { none },
  align: left + top,
  inset: 5pt,
    [*Limite*],
    [*Statut*],
    [L'aire sous la courbe égale celle du modèle vrai, ce qui ne prouve rien sur l'estimation],
    [déclaré ; le portefeuille construit n'a qu'une variable d'emprunteur, donc le classement est le même pour toute fonction croissante de cette variable],
    [L'échantillon Freddie Mac exige une inscription (usage non commercial) : les moteurs ne sont pas encore confrontés à de vrais prêts hypothécaires ; le chargeur et le protocole les attendent],
    [déclaré ; dépôt manuel documenté],
    [Le miroir canadien se limite à la série Valet des provisions ; les arriérés provinciaux (régressions de Pugh, Webley et Wang, 2026) restent à répliquer],
    [reconnu ; suite déclarée de la fiche],
    [LGD fixée à 25 % (précepte), EAD constantes : pas de modèle de LGD ni d'amortissement],
    [choix déclaré],
    [Le seuil de stade 2 (PD doublée) est une règle simple ; IFRS 9 admet d'autres critères (30 jours d'arriérés, listes de surveillance)],
    [déclaré],
    [La grille de cotation d'Enbridge est un précepte interne sans facteur qualitatif : l'écart au BBB des agences est structurel et commenté, pas corrigé],
    [déclaré, c'est l'enseignement du dossier],
    [Le classeur Excel est en .xlsx à formules ; la macro VBA de sensibilité de la fiche demanderait un .xlsm],
    [à venir],
)

== 8. Crédits, licence, citation

Shumway, T. (2001), « Forecasting Bankruptcy More Accurately: A Simple Hazard Model » ; Vasicek, O. (2002) ; Comité de Bâle (2005), « An Explanatory Note on the Basel II IRB Risk Weight Functions » ; BCBS d350 (2015) sur l'ECL ; OSFI, ligne directrice Normes de fonds propres, chapitre 5 (paramètres rapportés) ; Données : SEC EDGAR (domaine public), Banque du Canada Valet (licence ouverte), Freddie Mac (usage non commercial, non redistribué, non téléchargé ici). Code : Guillaume Vaudescal, 2026, licence MIT. Exercice d'analyse, pas un conseil de crédit.
