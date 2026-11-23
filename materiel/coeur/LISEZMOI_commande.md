# Cœur du dé connecté Mandragore — D-core v0.3 — commande JLCPCB

## Contenu
- `gerbers_de_core_v0.3.zip` : Gerbers 4 couches + perçage (à téléverser tel quel)
- `BOM_de_core.csv` : nomenclature au format JLCPCB (toutes les lignes ont une référence LCSC)
- `CPL_de_core.csv` : placement des composants (18 composants, 2 faces)
- `kicad/` : projet KiCad 7 (carte routée) et scripts de génération

## Options de commande PCB
| Option | Valeur |
|---|---|
| Couches | 4 |
| Dimensions | disque Ø16 mm |
| Épaisseur | 0,8 mm |
| Empilement | défaut JLC (In1 = plan de masse, In2 = signaux) |
| Piste / espacement minimum | 0,127 / 0,10 mm |
| Via | 0,45 / 0,25 mm |
| Recouvrement des vias | **Tented (vias recouvertes)** — obligatoire : des vias passent sous le module |
| Finition | ENIG conseillé (module LGA + pastilles fines) |
| Quantité | 5 |

La carte fait moins de 70 mm : accepter les **bords d'assemblage ajoutés par JLCPCB** (edge rails) ou leur panelisation si la page de commande le demande.

## Options d'assemblage (PCBA)
- **Standard PCBA, deux faces** (composants dessus et dessous).
- Le module **BC832 (C6470192)** exige un **contrôle aux rayons X** (proposé automatiquement).
- **Vérifier l'aperçu de placement** avant de payer : les rotations des composants du dessous et du module BC832 doivent être contrôlées dans la visionneuse JLC (antenne du module vers le bord de la carte, broche 1 en haut à gauche côté antenne).

## Composants à souder à la main (non fournis par JLC)
| Pastille (dessous) | À relier à |
|---|---|
| BAT+ / BAT− | pile rechargeable LIR1254 à languettes (3,7 V, Ø12 mm) |
| COIL1 + BAT− | bobine réceptrice logée dans la coque (D20 : 72 spires de fil émaillé 0,1 mm, Ø7,5 × 1,0 mm ; autres dés : 65 spires, Ø10 mm) — le second fil de la bobine se soude sur BAT− (masse) |
| G1, G2, G3, G4 | les 4 groupes de pastilles capacitives de la coque |
| SWDIO, SWCLK, VDD, GND | programmeur SWD (premier chargement du firmware) |

## Brochage pour le firmware (nRF52832)
| Fonction | Broche nRF |
|---|---|
| I2C SDA / SCL (LIS2DH12, adresse 0x18) | P0.26 / P0.27 |
| Interruption accéléromètre (INT1) | P0.03 |
| Tension pile (pont 1 MΩ / 1 MΩ : VBAT/2) | P0.02 / AIN0 |
| État de charge (CHRG, actif bas, pull-up interne) | P0.01 |
| Groupes capacitifs G1 / G2 / G3 / G4 | P0.11 / P0.12 / P0.13 / P0.18 |
| Court-circuit de la bobine (Q1, haut = court-circuit) | P0.20 |

- Pas de quartz 32 kHz : utiliser l'horloge basse fréquence RC interne (LFRC).
- Convertisseur DC-DC du nRF : **désactivé** (pas d'inductances).
- Batterie : mesure sur AIN0 (P0.02) d'un pont 1 MΩ / 1 MΩ, donc VBAT/2 ; temps d'acquisition SAADC de 40 µs (source à haute impédance).
- Pas de LED (depuis la v0.2) (invisible dans un dé peint) ; état et charge passent par le Bluetooth.
- Charge à ≈30 mA (R1 = 33 kΩ sur le TP4054).
- Recharge sans fil : accord série par C5 = 1 nF C0G (résonance ≈ 1 MHz avec la bobine de 24 µH), doubleur BAT54S, zener 5,6 V de protection.
- Pile pleine (≥ 4,15 V) : le firmware met P0.20 à l'état haut, Q1 court-circuite la bobine, la zener ne dissipe plus rien ; relâché à 4,0 V.

## Points à valider sur prototype
1. **Recharge sans fil** : simulée avec l'émetteur de la boîte (1 MHz) — 5,0 à 5,7 V redressés selon les tolérances (Monte-Carlo). À mesurer sur le premier prototype : tension sur C6 dé posé, puis pile pleine (court-circuit actif).
2. **Zener Z1** : ne travaille plus qu'en protection transitoire grâce au court-circuit de la bobine.
3. **Portée Bluetooth** : la pile sous l'antenne réduit la portée (accepté par le fabricant du module pour ce montage).
4. **Empreinte du BC832** : établie d'après la fiche technique Fanstel (pas 1,1 mm) et recoupée avec une bibliothèque indépendante ; à confirmer sur le module reçu avant la première commande en série.

## Changements depuis la v0.2
- Ajout de Q1 (2N7002T, SOT-523) et R4 (100 kΩ) : court-circuit de la bobine pile pleine.
- C3 supprimé (accord parallèle inutile), C5 passe de 1 µF à 1 nF C0G (accord série).
- Pastille L2 supprimée : le retour de bobine se soude sur BAT−.

## Contrôles effectués
- DRC KiCad : 0 violation de cuivre, 0 connexion manquante (restent des avertissements de sérigraphie sans effet).
- Toutes les références LCSC et les brochages ont été vérifiés dans la base EasyEDA/JLC.
