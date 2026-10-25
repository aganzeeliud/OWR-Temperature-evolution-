# Climat et forêts de la Réserve de faune à okapis

Tableau de bord autonome consacré à l’évolution du climat et du couvert arboré dans la Réserve de faune à okapis, en Ituri (République démocratique du Congo). Il réunit une série météorologique journalière de 1986 à 2026, les estimations annuelles de perte de couvert arboré jusqu’en 2025 et des détections provisoires d’alertes satellitaires pour 2026.

## Accès au projet

- **Tableau de bord en français :** [consulter `index.html` dans le dépôt](https://github.com/aganzeeliud/OWR-Temperature-evolution-/blob/main/index.html) · [télécharger le fichier HTML autonome](https://raw.githubusercontent.com/aganzeeliud/OWR-Temperature-evolution-/main/index.html)
- **Dépôt et historique :** [aganzeeliud/OWR-Temperature-evolution-](https://github.com/aganzeeliud/OWR-Temperature-evolution-)
- **Projet Power BI :** [OWR_Climate.pbip](https://github.com/aganzeeliud/OWR-Temperature-evolution-/blob/main/OWR_Climate.pbip)
- **Guide Power BI :** [README_POWERBI.md](README_POWERBI.md)

Le tableau de bord propose cinq onglets en français : **Vue d’ensemble**, **Activités minières**, **Téléchargements**, **Références scientifiques** et **Méthode & vérifications**. Le fichier HTML intègre les données météo utilisées par ses graphiques et peut être ouvert dans un navigateur récent. Pour utiliser aussi ses liens de téléchargement locaux, placez les fichiers CSV dans le même dossier que la page HTML. GitHub Pages n’étant pas activé pour ce dépôt, ces liens donnent accès au fichier source ou à son téléchargement, et non à une page interactive hébergée.

## Données téléchargeables

| Fichier | Contenu | Période / couverture |
|---|---|---|
| [`Meteo_owr.csv`](Meteo_owr.csv) | Date, année, mois, jour, températures maximales et minimales, précipitations | 1986-01-01 – 2026-10-25 |
| [`TreeCoverLoss_owr.csv`](TreeCoverLoss_owr.csv) | Estimation de la perte annuelle de couvert arboré en hectares | 2001–2025 |
| [`ForestAlerts_2026_owr.csv`](ForestAlerts_2026_owr.csv) | Détections mensuelles de pixels d’alerte, date d’observation et statut | 2026, observations jusqu’au 2026-10-04 |

Les fichiers utilisent des en-têtes de colonnes explicites, des dates ISO (`AAAA-MM-JJ`) et des valeurs numériques directement exploitables dans un tableur, Python, R ou Power BI. Les en-têtes CSV d’origine sont conservés pour assurer la compatibilité avec le modèle Power BI.

## Utiliser le tableau de bord

La page est organisée en cinq onglets :

1. **Vue d’ensemble** — filtres d’années, indicateurs météo, tendances annuelles et saisonnières, indicateurs de perte de couvert et alertes.
2. **Activités minières** — série de perte du couvert GFW du dépôt et comparateur par zone pour les résultats exportés Landsat/Sentinel et UMD/Hansen.
3. **Téléchargements** — liens vers les exports CSV, le fichier HTML et le projet Power BI.
4. **Références scientifiques** — liens vers les documentations et sources de données.
5. **Méthode & vérifications** — calcul des indicateurs, contrôles et limites d’interprétation.

Dans la vue d’ensemble, sélectionnez une plage d’années et choisissez d’afficher la température ou les précipitations. Les indicateurs et les graphiques climatiques sont recalculés à partir des jours disponibles. La comparaison forestière présente séparément les estimations annuelles de perte et les alertes provisoires de 2026.

L’onglet **Activités minières** présente une chaîne reproductible Google Earth Engine et les sources satellitaires pour 2000–2026. Le calcul doit être lancé par un utilisateur Earth Engine après import de la limite de la réserve ; les résultats ne sont pas calculés ni fournis dans ce dépôt. Sans inventaire de sites vérifiés, les changements détectés restent des signaux candidats et ne sont pas attribués à l’exploitation minière.

### Lancer l’analyse minière (Google Earth Engine)

1. Téléchargez [`earth_engine/okapi_mining_deforestation.js`](earth_engine/okapi_mining_deforestation.js), ouvrez-le dans le [Code Editor Earth Engine](https://code.earthengine.google.com/) et remplacez `reserveAsset` par l’identifiant d’un asset de limite de réserve que vous êtes autorisé à utiliser.
2. Pour comparer les changements à des mines, importez d’abord un inventaire géoréférencé vérifié dans vos assets Earth Engine, puis renseignez `miningSitesAsset`. Chaque élément doit avoir les propriétés numériques `start_year` et `end_year` pour ne compter que les sites actifs l’année considérée. Les points ou polygones fournis servent à calculer la perte candidate dans un rayon de 500 m ; les sites ne sont pas découverts automatiquement.
3. Exécutez le script : la carte permet de parcourir les années et les couches, dont la perte annuelle GFW/UMD-Hansen (2001–2024); créez la tâche d’export CSV dans l’onglet **Tasks** de l’éditeur. L’export contient deux lignes par année, une pour la réserve et une pour la couronne extérieure 0–10 km, avec les hectares candidats, la référence Hansen (2001–2024), le nombre d’images et un statut de disponibilité.
4. Dans l’onglet **Activités minières** du tableau de bord, chargez ce CSV dans **Comparaison croisée · GFW et télédétection**, puis choisissez la réserve ou la couronne. La série GFW du dépôt (2001–2025) s’affiche à côté des valeurs Hansen et des transitions candidates exportées. La série GFW du dépôt concerne seulement la réserve ; le comparateur ne l’étend pas artificiellement à la couronne. L’import du CSV est effectué localement dans le navigateur.
5. Vérifiez visuellement les sites et les transitions avant d’interpréter ou de publier les résultats. L’aperçu 2026 est partiel. Un compte Earth Engine, un asset de périmètre et l’exécution des tâches d’export sont nécessaires ; ils ne sont pas accessibles depuis cette page statique.

Le script calcule les indices NDVI, NBR, MNDWI et BSI sur des composites annuels propres à chaque capteur Landsat 5/7/8/9 et Sentinel-2, puis combine les composites d’indices et recherche les transitions annuelles potentielles de forêt vers sol nu à 30 m. L’export comprend aussi une couche de référence UMD/Hansen v1.12 pour 2001–2024, avec la définition de couvert arboré 2000 ≥ 30 %. Sentinel-1 VV/VH fournit une couche radar complémentaire; ASTER L1T est affiché en radiance numérique uniquement pour l’inspection; MODIS Terra/Aqua à 500 m sert de contexte régional et n’est pas mélangé au calcul à 30 m. Les résolutions et réponses spectrales diffèrent : les indices optiques ne sont pas une harmonisation de réflectance validée et les seuils sont des paramètres de dépistage à calibrer avec des observations de terrain. La version actuelle de l’API GFW est v1.13, mais le CSV du dépôt ne consigne pas sa version d’extraction. Les catalogues Earth Engine consultés pour Sentinel-1 et MODIS indiquent des dates de fin en 2025 ; leur couverture 2026 n’est pas présumée, et le comptage de scènes/statut de l’export doit être examiné avant interprétation.

## Sources et périmètre

- **Météo :** [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) et données publiées dans [`Meteo_owr.csv`](Meteo_owr.csv). Les valeurs de grille sont des estimations pour les coordonnées approximatives de la réserve, et non des mesures provenant d’une station météo locale dans l’aire protégée.
- **Perte de couvert arboré :** [jeu de données UMD Tree Cover Loss de Global Forest Watch](https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss/latest), résumé annuellement pour la zone d’étude. L’année 2000 sert de référence du couvert ; les observations annuelles de perte commencent en 2001.
- **Croisement GFW/Hansen :** le comparateur du tableau de bord combine visuellement, sans les additionner, les valeurs annuelles de [`TreeCoverLoss_owr.csv`](TreeCoverLoss_owr.csv) (réserve, 2001–2025 ; version source non consignée) et les valeurs Hansen ainsi que les transitions optiques candidates de l’export Earth Engine (réserve et couronne externe, 2000–2026). Le produit [UMD/Hansen v1.12](https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12) couvre 2001–2024, avec seuil `treecover2000 ≥ 30 %`. L’API GFW consultée indique actuellement la version v1.13 ; les différences de version, seuil, période et géométrie doivent être documentées. L’année 2000 est une référence, pas une année de perte ; pour 2026, seules des transitions optiques candidates partielles peuvent être montrées, aucune perte annuelle GFW/Hansen finalisée n’est incluse.
- **Référence scientifique :** Hansen, M. C. et al. (2013). [High-Resolution Global Maps of 21st-Century Forest Cover Change](https://doi.org/10.1126/science.1244693) [Cartes mondiales à haute résolution de l’évolution du couvert forestier au XXIe siècle]. *Science*, 342(6160), 850–853.
- **Zone d’étude fournie :** [Global Nature Watch](https://gfw.global/eWfDix). La géométrie de l’AOI n’étant pas exposée dans la réponse publique utilisée pour l’extraction, le périmètre substitutif est la [relation 401017 de la Réserve de faune à okapis dans OpenStreetMap](https://www.openstreetmap.org/relation/401017).
- **Alertes forestières :** détections mensuelles intégrées de pixels d’alerte, fournies dans [`ForestAlerts_2026_owr.csv`](ForestAlerts_2026_owr.csv), version `v20261025`.
- **Sources satellitaires pour l’analyse minière :** [Landsat 5](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LT05_C02_T1_L2), [Landsat 7](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LE07_C02_T1_L2), [Landsat 8](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2), [Landsat 9](https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2), [Sentinel-2 harmonisé](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED), [Sentinel-1 GRD](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD), [ASTER L1T](https://developers.google.com/earth-engine/datasets/catalog/ASTER_AST_L1T_003), [MODIS Terra](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD09A1) et [MODIS Aqua](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MYD09A1). La disponibilité réelle dépend des dates d’acquisition et de l’ingestion dans Earth Engine ; le script exporte un nombre de scènes pour contrôler la couverture, notamment pour 2026.

## Méthode et vérifications

- Les moyennes journalières/annuelles excluent les valeurs absentes. Les précipitations annuelles sont la somme des valeurs journalières disponibles ; les valeurs manquantes ne sont ni interpolées ni estimées dans le tableau de bord.
- Le fichier météo compte **14 908 jours** et conserve des lacunes de source en 1991 : 31 valeurs de température maximale, 31 de température minimale et 215 de précipitations sont manquantes.
- Les indicateurs forestiers annuels sont calculés sur les valeurs 2001–2025 exportées. La perte de couvert arboré n’est pas nécessairement synonyme de déforestation permanente.
- Le total de **131 978 alertes** en 2026 correspond à des détections de pixels jusqu’au 4 octobre 2026. Il ne représente ni une perte de forêt confirmée, ni une superficie en hectares uniques ; des détections répétées sont possibles. Octobre est partiel.
- Les alertes 2026 et la perte annuelle de couvert arboré sont des produits distincts et ne sont pas additionnés.
- Le tableau de bord fournit des contrôles de cohérence et de traçabilité, mais ne constitue pas une validation indépendante des produits satellitaires ou des estimations météorologiques à la source.
- Le script minier exporte une **perte forestière candidate**, pas une cartographie validée de mines ou de déforestation attribuable aux mines. Les nuages, mélanges de capteurs, seuils d’indices, perturbations non minières et changements saisonniers exigent validation visuelle et terrain. Un résultat de proximité avec un site minier ne démontre pas la causalité.

## Projet Power BI

Le dépôt fournit un projet **Power BI Project (PBIP)**, et non un fichier PBIX final. Ouvrez [`OWR_Climate.pbip`](OWR_Climate.pbip) dans Power BI Desktop, actualisez les trois tables à partir des CSV publics du dépôt, puis choisissez **Fichier → Enregistrer sous → Power BI Desktop (.pbix)**. Power BI Desktop est nécessaire à cette conversion ; il n’est pas disponible dans l’environnement Linux utilisé pour préparer le projet. Les détails sont dans [README_POWERBI.md](README_POWERBI.md).

## Références complémentaires

- [Global Forest Watch](https://www.globalforestwatch.org/)
- [Documentation des modèles Open-Meteo](https://open-meteo.com/en/docs)
- [OpenStreetMap — relation 401017](https://www.openstreetmap.org/relation/401017)
