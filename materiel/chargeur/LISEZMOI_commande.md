# Carte émettrice de la boîte-chargeur MCDice — v0.1 — commande JLCPCB

## Contenu
- `gerbers_chargeur_v0.1.zip` : Gerbers 2 couches + perçage (à téléverser tel quel)
- `BOM_chargeur.csv` : nomenclature au format JLCPCB (une référence LCSC par ligne)
- `CPL_chargeur.csv` : placement (tous les composants sont **en face dessous**)
- `kicad/` : projet KiCad 7 (carte routée), scripts de génération et de simulation

## Options de commande PCB
| Option | Valeur |
|---|---|
| Couches | 2 |
| Dimensions | 152 × 82 mm (encoches d'angle Ø8,2 pour les bossages de la boîte) |
| Épaisseur | **0,8 mm** (les spirales et l'accord ont été calculés pour cette épaisseur) |
| Cuivre | 1 oz |
| Piste / espacement minimum | 0,2 / 0,127 mm (spirales : piste 0,2, espace 0,15) |
| Via | 0,6 / 0,3 mm |
| Recouvrement des vias | Tented |
| Finition | HASL sans plomb ou ENIG |
| Quantité | 5 |

## Options d'assemblage (PCBA)
- **Standard PCBA, une face : face du dessous (Bottom)**. La face du dessus ne porte que les spirales et le plan de masse, car elle est plaquée contre le plancher de la boîte.
- Le connecteur USB-C (C2765186) a 4 pattes de fixation traversantes : JLC les soude (assemblage mixte), accepter le supplément s'il est proposé.
- **Vérifier l'aperçu de placement** avant de payer : les rotations des composants en face dessous (surtout U3 CH32V203, U2 UCC27524, les SOT-23 et J1) doivent correspondre aux empreintes.

## Schéma en bref
| Bloc | Composants |
|---|---|
| Entrée USB-C 5 V (puits, CC1/CC2 à 5,1 kΩ) | J1, R1, R2, C1, C2 |
| 3,3 V | U1 XC6206P332, C3, C4 |
| Demi-pont 1 MHz commun | U2 UCC27524 (pilote), Q1 AO3401A (haut), Q2 AO3400A (bas), C5, C6, C7, R3, R4 |
| Microcontrôleur | U3 CH32V203C8T6, Y1 8 MHz, C8–C12, C14, R5 + SW1 (BOOT), D1 + R6 (voyant) |
| Emplacement k (k = 1…7) | C2k 10 nF + C3k 2,2 nF C0G (accord), spirale gravée, Q1k AO3400A (mise en service), R1k 100 kΩ, R2k + R3k 2 × 2,2 Ω (mesure), D1k B5819W + C4k 100 nF + R4k 100 kΩ (détecteur de crête) |

## Brochage du CH32V203 (pour le firmware `firmware/chargeur`)
| Fonction | Broche |
|---|---|
| Demi-pont : TIM1_CH1 → INA (P), TIM1_CH1N → INB (N) | PA8, PB13 |
| Mise en service des emplacements 1 à 7 | PC13, PC14, PA5, PA4, PB4, PB10, PA7 |
| Mesure de crête des emplacements 1 à 7 (ADC) | PA0, PA1, PA2, PA3, PB1, PB0, PA6 |
| Voyant | PB11 |
| USB (mise à jour) | PA11 / PA12 |
| SWD | PA13 / PA14 (pastilles TP1/TP2) |

## Programmation
- **Par USB** : maintenir le bouton BOOT en branchant l'USB-C (BOOT0 = 1). Le chargeur d'amorçage WCH apparaît, et `wchisp` ou WCHISPTool charge le programme.
- **Par SWD** : sonde WCH-LinkE sur les pastilles SWDIO, SWCLK, 3V3, GND.
- La fiche USB-C se branche dans les deux sens (les deux paires D+/D− du connecteur sont reliées).

## Points à valider sur prototype
1. Seuil de présence `SEUIL_VIDE_V` (lire les crêtes sur le port série).
2. Tension redressée dans un dé posé (attendu ≈ 5,7 V d'après la simulation).
3. Échauffement des résistances de mesure (2 × 2,2 Ω en 1206) : au plus ≈ 0,1 W chacune en charge.
