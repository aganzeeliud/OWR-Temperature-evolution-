# Climat et forêts de la Réserve de faune à okapis

Tableau de bord autonome consacré à l’évolution du climat et du couvert arboré dans la Réserve de faune à okapis, en Ituri (République démocratique du Congo). Il réunit une série météorologique journalière de 1986 à 2026, les estimations annuelles de perte de couvert arboré jusqu’en 2025 et des détections provisoires d’alertes satellitaires pour 2026.

## Accès au projet

- **Tableau de bord en français :** [consulter `index.html` dans le dépôt](https://github.com/aganzeeliud/OWR-Temperature-evolution-/blob/main/index.html) · [télécharger le fichier HTML autonome](https://raw.githubusercontent.com/aganzeeliud/OWR-Temperature-evolution-/main/index.html)
- **Dépôt et historique :** [aganzeeliud/OWR-Temperature-evolution-](https://github.com/aganzeeliud/OWR-Temperature-evolution-)
- **Projet Power BI :** [OWR_Climate.pbip](https://github.com/aganzeeliud/OWR-Temperature-evolution-/blob/main/OWR_Climate.pbip)
- **Guide Power BI :** [README_POWERBI.md](README_POWERBI.md)

Le tableau de bord propose quatre onglets en français : **Vue d’ensemble**, **Téléchargements**, **Références scientifiques** et **Méthode & vérifications**. Le fichier HTML intègre les données météo utilisées par ses graphiques et peut être ouvert dans un navigateur récent. Pour utiliser aussi ses liens de téléchargement locaux, placez les fichiers CSV dans le même dossier que la page HTML. GitHub Pages n’étant pas activé pour ce dépôt, ces liens donnent accès au fichier source ou à son téléchargement, et non à une page interactive hébergée.

## Données téléchargeables

| Fichier | Contenu | Période / couverture |
|---|---|---|
| [`Meteo_owr.csv`](Meteo_owr.csv) | Date, année, mois, jour, températures maximales et minimales, précipitations | 1986-01-01 – 2026-10-25 |
| [`TreeCoverLoss_owr.csv`](TreeCoverLoss_owr.csv) | Estimation de la perte annuelle de couvert arboré en hectares | 2001–2025 |
| [`ForestAlerts_2026_owr.csv`](ForestAlerts_2026_owr.csv) | Détections mensuelles de pixels d’alerte, date d’observation et statut | 2026, observations jusqu’au 2026-10-04 |

Les fichiers utilisent des en-têtes de colonnes explicites, des dates ISO (`AAAA-MM-JJ`) et des valeurs numériques directement exploitables dans un tableur, Python, R ou Power BI. Les en-têtes CSV d’origine sont conservés pour assurer la compatibilité avec le modèle Power BI.

## Utiliser le tableau de bord

La page est organisée en quatre onglets :

1. **Vue d’ensemble** — filtres d’années, indicateurs météo, tendances annuelles et saisonnières, indicateurs de perte de couvert et alertes.
2. **Téléchargements** — liens vers les exports CSV, le fichier HTML et le projet Power BI.
3. **Références scientifiques** — liens vers les documentations et sources de données.
4. **Méthode & vérifications** — calcul des indicateurs, contrôles et limites d’interprétation.

Dans la vue d’ensemble, sélectionnez une plage d’années et choisissez d’afficher la température ou les précipitations. Les indicateurs et les graphiques climatiques sont recalculés à partir des jours disponibles. La comparaison forestière présente séparément les estimations annuelles de perte et les alertes provisoires de 2026.

## Sources et périmètre

- **Météo :** [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) et données publiées dans [`Meteo_owr.csv`](Meteo_owr.csv). Les valeurs de grille sont des estimations pour les coordonnées approximatives de la réserve, et non des mesures provenant d’une station météo locale dans l’aire protégée.
- **Perte de couvert arboré :** [jeu de données UMD Tree Cover Loss de Global Forest Watch](https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss/latest), résumé annuellement pour la zone d’étude. L’année 2000 sert de référence du couvert ; les observations annuelles de perte commencent en 2001.
- **Référence scientifique :** Hansen, M. C. et al. (2013). [High-Resolution Global Maps of 21st-Century Forest Cover Change](https://doi.org/10.1126/science.1244693) [Cartes mondiales à haute résolution de l’évolution du couvert forestier au XXIe siècle]. *Science*, 342(6160), 850–853.
- **Zone d’étude fournie :** [Global Nature Watch](https://gfw.global/eWfDix). La géométrie de l’AOI n’étant pas exposée dans la réponse publique utilisée pour l’extraction, le périmètre substitutif est la [relation 401017 de la Réserve de faune à okapis dans OpenStreetMap](https://www.openstreetmap.org/relation/401017).
- **Alertes forestières :** détections mensuelles intégrées de pixels d’alerte, fournies dans [`ForestAlerts_2026_owr.csv`](ForestAlerts_2026_owr.csv), version `v20261025`.

## Méthode et vérifications

- Les moyennes journalières/annuelles excluent les valeurs absentes. Les précipitations annuelles sont la somme des valeurs journalières disponibles ; les valeurs manquantes ne sont ni interpolées ni estimées dans le tableau de bord.
- Le fichier météo compte **14 908 jours** et conserve des lacunes de source en 1991 : 31 valeurs de température maximale, 31 de température minimale et 215 de précipitations sont manquantes.
- Les indicateurs forestiers annuels sont calculés sur les valeurs 2001–2025 exportées. La perte de couvert arboré n’est pas nécessairement synonyme de déforestation permanente.
- Le total de **131 978 alertes** en 2026 correspond à des détections de pixels jusqu’au 4 octobre 2026. Il ne représente ni une perte de forêt confirmée, ni une superficie en hectares uniques ; des détections répétées sont possibles. Octobre est partiel.
- Les alertes 2026 et la perte annuelle de couvert arboré sont des produits distincts et ne sont pas additionnés.
- Le tableau de bord fournit des contrôles de cohérence et de traçabilité, mais ne constitue pas une validation indépendante des produits satellitaires ou des estimations météorologiques à la source.

## Projet Power BI

Le dépôt fournit un projet **Power BI Project (PBIP)**, et non un fichier PBIX final. Ouvrez [`OWR_Climate.pbip`](OWR_Climate.pbip) dans Power BI Desktop, actualisez les trois tables à partir des CSV publics du dépôt, puis choisissez **Fichier → Enregistrer sous → Power BI Desktop (.pbix)**. Power BI Desktop est nécessaire à cette conversion ; il n’est pas disponible dans l’environnement Linux utilisé pour préparer le projet. Les détails sont dans [README_POWERBI.md](README_POWERBI.md).

## Références complémentaires

- [Global Forest Watch](https://www.globalforestwatch.org/)
- [Documentation des modèles Open-Meteo](https://open-meteo.com/en/docs)
- [OpenStreetMap — relation 401017](https://www.openstreetmap.org/relation/401017)
