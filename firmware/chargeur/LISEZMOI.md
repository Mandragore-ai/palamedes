# Firmware de la boîte-chargeur MCDice (CH32V203C8T6)

## Outils
- Arduino IDE 2 + cœur **« CH32 MCU EVT Boards »** (openwch/arduino_core_ch32, URL de cartes : `https://github.com/openwch/board_manager_files/raw/main/package_ch32v_index.json`).
- Carte : `CH32V20x_EVT`, choix « CH32V203C8 », horloge « 144MHz External » (quartz 8 MHz de la carte).

## Chargement
- **Par USB-C** : maintenir le bouton BOOT de la carte en branchant le câble. Le chargeur d'amorçage WCH apparaît, puis on charge le `.bin` avec `wchisp flash chargeur.bin` ou WCHISPTool.
- **Par SWD** : une sonde WCH-LinkE sur les pastilles SWDIO / SWCLK / 3V3 / GND, téléversement direct depuis l'IDE.

## Réglages (`chargeur.ino`)
| Constante | Rôle | Valeur |
|---|---|---|
| `F_HZ` | fréquence d'émission (résonance spirale + 12,2 nF) | 1 MHz |
| `DEADTIME_DTG` | temps mort entre les deux transistors du demi-pont | ≈ 49 ns |
| `SEUIL_VIDE_V` | crête au-dessus de laquelle l'emplacement est vide | 0,85 V, **à confirmer au premier essai** |
| `DUREE_CHARGE` | durée maximale d'une charge | 4 h |

Le port série (UART1, PA9/PA10, 115 200 bauds) affiche toutes les 5 s l'état et la tension de crête de chaque emplacement : c'est ce qui sert à régler le seuil. Valeurs attendues d'après la simulation : vide ≈ 1,2 V, dé posé 0,1 à 0,4 V.

## État
- **Compile sans erreur** (cœur WCH ch32v 1.0.7, carte `CH32V203C8`, horloge « 144MHz External ») : 31 % de la flash, 6 % de la RAM.
  `arduino-cli compile -b "WCH:ch32v:CH32V20x_EVT:pnum=CH32V203C8,clock=144MHz_HSE" chargeur`
- Programme compilé prêt à charger : `../binaires/chargeur_mcdice.bin`.
- Pas encore essayé sur le matériel. La sortie série passe par l'UART (PA9/PA10), pas par l'USB.
