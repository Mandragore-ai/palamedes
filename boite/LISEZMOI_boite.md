# Boîte-chargeur MCDice — set de 7 dés

La boîte recharge sans fil les 7 dés d'un set. Elle est alimentée par une prise USB-C 5 V et contient une seule carte électronique, la **carte émettrice MCDice** (dossier `jlcpcb_chargeur/`, commandée montée chez JLCPCB). Il n'y a ni module du commerce ni câblage à faire.

## Pièces imprimées
- `boite_chargeur_corps.stl` (157 × 87 × 12,6 mm) : 7 logements à la forme exacte de chaque dé posé sur sa face de recharge, avec un jeu de 0,35 mm et un plancher de 0,6 mm sous chaque dé. Dessous se trouve un creux technique de 7 mm pour la carte, avec une ouverture USB-C sur le petit côté gauche.
- `boite_chargeur_fond.stl` : fond de 2 mm, fixé par 4 vis M2 × 8 autotaraudeuses. Il porte **un téton Ø4 sous chaque spirale**, qui plaque la carte contre le plancher.
- Impression FDM en PLA ou PETG. Planchers de 0,6 mm : couches de 0,2 mm, remplissage 100 %.

## Montage
1. Poser la carte dans le creux du corps, **face sans composants vers le plancher**. Les encoches d'angle laissent passer les bossages de vis, et la prise USB-C vient face à l'ouverture.
2. Optionnel : un point de colle ou d'adhésif double face au centre de la carte.
3. Visser le fond. Les tétons appuient sur la carte au centre de chaque spirale, ce qui garantit l'écart avec la bobine du dé (≈ 1,5 à 2 mm).
4. Brancher un chargeur USB-C 5 V de 2 A ou plus.

## Fonctionnement
- Chaque logement est sondé 3 ms par seconde. S'il trouve un dé (courant d'émission bas), il le charge, puis s'arrête au bout de 4 h ou dès qu'on retire le dé.
- Le dé coupe lui-même sa réception quand sa pile est pleine. L'état de charge s'affiche dans Mandragore par Bluetooth.
- Voyant sous la carte, visible boîte ouverte : clignote = au moins un dé en charge, fixe = charges terminées.
- Consommation : environ 0,1 à 0,5 W par dé en charge, rien à vide (hors sondes).

## Logements
- D4* : en attendant la décision sur le D4, logement d'un D8 numéroté deux fois de 1 à 4 (même cœur).
- D% : deuxième D10, pour les dizaines du D100.
- Tailles retenues (face à face) : D6 20, D8 22, D10 23, D12 23, D20 22,5 mm. Les coques des autres dés devront respecter ces tailles.

## Ce qui a été simulé (scripts `sim_wpt*.py`, `sim_tx_carte.py`)
- Spirale gravée telle que dessinée : 2,0 µH, 1,1 Ω ; accord 10 nF + 2,2 nF C0G (résonance 1,02 MHz, émission à 1 MHz).
- Tension redressée dans le dé : 5,7 V pour un écart de 1,5 à 2,5 mm et un décentrage jusqu'à 1,5 mm. Avec des tolérances de ±5 % sur les composants, elle ne descend pas sous 5,7 V.
- Logement vide : 0,97 A efficace, d'où la détection de présence et l'arrêt automatique.

## À vérifier sur le premier prototype
1. Lire sur le port série du chargeur (115 200 bauds) la tension de crête d'un logement vide et d'un logement occupé, puis ajuster `SEUIL_VIDE_V` dans le firmware si besoin.
2. Mesurer la tension sur C6 dans un dé posé (attendu ≈ 5,7 V).
3. Essayer d'abord un seul dé avant d'imprimer les 7 coques.
