#!/bin/sh
# rendu PNG dessus/dessous d'un PCB
PCB=$1; OUTD=$2; mkdir -p $OUTD
kicad-cli pcb export svg -o $OUTD/top.svg --layers F.Cu,F.SilkS,F.Fab,F.CrtYd,Edge.Cuts,F.Mask --exclude-drawing-sheet --page-size-mode 2 $PCB >/dev/null
kicad-cli pcb export svg -o $OUTD/bot.svg --layers B.Cu,B.SilkS,B.Fab,B.CrtYd,Edge.Cuts --mirror --exclude-drawing-sheet --page-size-mode 2 $PCB >/dev/null
kicad-cli pcb export svg -o $OUTD/in2.svg --layers In2.Cu,In1.Cu,Edge.Cuts --exclude-drawing-sheet --page-size-mode 2 $PCB >/dev/null
for f in top bot in2; do rsvg-convert -w 900 -b white $OUTD/$f.svg -o $OUTD/$f.png 2>/dev/null || convert -density 600 -background white $OUTD/$f.svg $OUTD/$f.png; done
