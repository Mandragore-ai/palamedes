# Firmware de départ — dé connecté Mandragore (D-core v0.3, D20)

**État : compile sans erreur ni avertissement** (cœur Adafruit nRF52 1.7.0, 25 % de la flash, 17 % de la RAM), **pas encore essayé sur le matériel**. Les points à vérifier en premier sont marqués « à vérifier » dans le code.

## Fichiers
- `de_mandragore/de_mandragore.ino` : le programme (Arduino, cœur « Adafruit nRF52 »)
- `de_mandragore/faces.h` : table des 20 faces (orientation, valeur, groupe de pastilles), générée depuis la géométrie de la coque
- `test_web_bluetooth.html` : page de test à ouvrir dans Chrome (ordinateur ou Android) — c'est la brique à reprendre dans Mandragore
- `variante_mcdice/` : variante de carte « MCDice » (copie de la Feather nRF52832 avec l'oscillateur RC interne) + `boards.local.txt`
- `binaires/` : programmes compilés — `de_mcdice.hex` (SWD), `de_mcdice_dfu.zip` (mise à jour Bluetooth), `chargeur_mcdice.bin` / `.hex` (boîte)

## Chaîne d'outils
1. Arduino IDE 2 + cœur **Adafruit nRF52** (gestionnaire de cartes).
2. **Variante MCDice** (fournie) : le BC832 n'a pas de quartz 32 kHz, il faut l'oscillateur RC interne (`USE_LFRC`), sinon le Bluetooth ne démarre pas. Installer : copier `variante_mcdice/variant.h` et `variant.cpp` dans `…/packages/adafruit/hardware/nrf52/<version>/variants/mcdice_bc832/`, et `boards.local.txt` à côté de `boards.txt`. La carte « MCDice (BC832, oscillateur RC) » apparaît alors dans l'IDE. Numéro Arduino = numéro P0.xx.
3. En ligne de commande : `arduino-cli compile -b adafruit:nrf52:mcdice de_mandragore`.
4. Premier chargement par **SWD** (pastilles SWDIO, SWCLK, VDD, GND sous la carte) avec une sonde J-Link, ou un Raspberry Pi Pico en « debugprobe » + OpenOCD :
   - d'abord `binaires/bootloader_s132_6.1.1.hex` : chargeur d'amorçage Adafruit 0.9.1 + SoftDevice S132 6.1.1 (MIT, Adafruit). Vérifié dans ses sources : il démarre le Bluetooth sur l'oscillateur RC interne quel que soit le modèle de carte, donc il convient au BC832 sans quartz.
   - puis `binaires/de_mcdice.hex`.
   - Effet de bord sans danger : ce chargeur d'amorçage tire P0.20 vers le haut (bouton DFU de la Feather) ; pendant les quelques dixièmes de seconde du démarrage, le transistor Q1 peut court-circuiter la bobine de recharge.
5. Mises à jour suivantes **par Bluetooth** : le firmware expose le service DFU « sans bouton » (BLEDfu). Avec nRF Connect ou Device Manager, choisir le dé puis `binaires/de_mcdice_dfu.zip`. La coque est remplie de résine, il n'y a plus d'accès au SWD ensuite : **faire une mise à jour Bluetooth complète sur le premier cœur avant de couler la résine.**

## Protocole Bluetooth
Service `6d616e64-7261-676f-7265-000000000001`
- Résultat (lecture + notification) `…0002` : 6 octets `[séquence, état, valeur, face, confiance %, type=20]`. États : 0 repos, 1 roule, 2 arrêté (valeur valide), 3 penché (à relancer).
- Commandes (écriture) `…0003` :
  - `01 r g b` couleur du joueur
  - `02 01` puis `02 02` étalonnage (face 1 en haut, puis face 2 en haut)
  - `03 m` mode capacitif : 0 coupé, 1 plateau à l'encre, 2 tablette, 3 les deux
  - `04 id` identité du dé (0–255)
- Service batterie standard : pourcentage calculé depuis la tension de la pile (pont diviseur sur AIN0).
- **Pile pleine sur le chargeur** : au-dessus de 4,15 V le firmware met P0.20 à l'état haut (Q1 court-circuite la bobine) et relâche à 4,0 V. La charge s'arrête donc à l'entrée en phase de tension constante (≈ 85–90 % de capacité), ce qui ménage aussi la pile. L'état est conservé en veille profonde.
- La commande `01 r g b` (couleur) est conservée pour une future version translucide avec LED ; sans effet depuis la v0.2.

## Signal capacitif
- **Plateau à l'encre (émission)** : sur le groupe de pastilles de la face posée, trame Manchester à 1 kbit/s, répétée 3 fois : `1010` + identité (8 bits) + valeur (5 bits) + somme de contrôle (3 bits). Les autres groupes sont reliés à la masse du dé, comme dans la simulation.
- **Tablette (tapotement)** : les 4 groupes ensemble ; « contact » = reliés à la masse du dé, « rien » = haute impédance. Créneaux de 50 ms : départ (150 ms de contact + 50 ms de vide) puis 13 bits (identité, valeur). La page de test décode ce signal.

## Correspondance groupes → broches (déjà dans `faces.h`)
| Groupe (faces) | Fil vers | Broche |
|---|---|---|
| 1 (1, 4, 8, 10, 16) | G3 | P0.13 |
| 2 (2, 6, 9, 13, 14) | G4 | P0.18 |
| 3 (3, 5, 7, 11, 12) | G2 | P0.12 |
| 4 (15, 17, 18, 19, 20) | G1 | P0.11 |

## Étalonnage
L'orientation exacte de l'accéléromètre dans le dé n'est connue qu'à quelques degrés près. Une fois le dé monté, avec la page de test : poser le dé **face 1 en haut**, cliquer « Étalonner : face 1 », puis **face 2 en haut** et « puis face 2 ». C'est enregistré en mémoire flash.

## Équité du dé
Le dé peut servir à se tester lui-même : enregistrer 500 lancers depuis la page de test, puis vérifier la répartition (test du χ² : chaque face devrait sortir environ 25 fois). En cas d'écart, ajuster le lest (pâte de tungstène, logement prévu dans la coque).
