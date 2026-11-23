# Montage du D20 Mandragore (22,5 mm face à face)

## Pièces
- `D20_coque_bas.stl`, `D20_coque_haut.stl` : les deux moitiés, plan de joint à plat (impression résine SLA conseillée, translucide si l'on veut voir la LED).
- `D20_patron_A4.pdf` : patron 1:1 (numéros, groupes, trous de fil) — gabarit pour le cuivre et la peinture.
- Le cœur D-core v0.2 assemblé, une pile LIR1254 à languettes, une bobine réceptrice **Ø7,6 mm maximum, 1,3 mm d'épaisseur** (voir la notice de la boîte-chargeur).
- Ruban de cuivre adhésif (ou encre conductrice), fil émaillé fin (0,1–0,2 mm), 3 goupilles en filament 1 mm.
- Résine d'enrobage **à prise lente / faible exothermie** (la pile craint la chaleur), pâte de tungstène (lest).

## Étapes
1. **Programmer et tester le cœur avant tout** : firmware, Bluetooth, mise à jour par Bluetooth, LED, accéléromètre. Après la coulée, plus aucun accès.
2. Souder la pile (BAT+ / BAT−) sous la carte, et deux fils fins d'environ 15 mm sur L1 / L2 pour la bobine.
3. Souder 4 fils fins aux pastilles G1–G4 du circuit (≈ 20 mm de long).
4. **Coque** : coller le cuivre dans les 20 logements triangulaires et sur les ponts entre faces d'un même groupe (une bande continue par groupe). **Face 1 : cuivre en peigne** (5 fentes, voir le patron), sinon la recharge ne passe pas. Vérifier au multimètre : 4 groupes isolés entre eux, et 5 faces reliées dans chaque groupe.
4 bis. Glisser la bobine au fond de son logement, sous la face 1 (moitié basse), fils vers le haut, et la coller.
5. Souder les fils de la bobine sur L1 / L2, puis poser le cœur dans la moitié basse, pile en bas, circuit en haut. Tourner le cœur pour aligner G3, G4 et G2 avec leurs trous ; le fil G1 fait un quart de tour.
6. Passer chaque fil dans son trou (faces 16, 14, 11, 15 sur le patron) et le relier au cuivre de son groupe (soudure rapide ou colle conductrice).
7. Mettre **≈ 0,22 g de pâte de tungstène** dans le logement de lest de la moitié haute (au-dessus du circuit).
8. Goupilles, collage des deux moitiés.
9. Couler la résine lentement par le trou de remplissage (le plus grand), jusqu'à ce qu'elle sorte par l'évent. En plusieurs fois s'il le faut, pour limiter l'échauffement.
10. Poncer, apprêt, peinture **non métallique** et numéros selon le patron (faces opposées = 21). Le cuivre reste caché sous la peinture.
11. Étalonnage en 2 poses depuis la page de test, puis 500 lancers pour vérifier l'équité. Ajuster le lest au prochain dé si besoin.

## Recharge
Poser le dé **face 1 en bas** dans son logement de la boîte-chargeur (la face 20 en haut).

## Chiffres clés
- Masse estimée ≈ 9,8 g.
- Paroi minimale 1,28 mm (1,13 mm sous les pastilles).
- Décalage du centre de gravité estimé à −0,16 mm sans lest.
