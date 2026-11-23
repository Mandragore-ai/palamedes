// Généré automatiquement par scripts/net_d20.py + make_shell.py — ne pas éditer à la main.
// Repère « palet » : z = normale du circuit (côté module), x/y = repère de la carte vu de dessus (y vers le haut).
#pragma once
#include <stdint.h>

#define NB_FACES 20
struct Face { float nx, ny, nz; uint8_t valeur; uint8_t groupe; };
// normale extérieure de chaque face, valeur peinte, groupe de pastilles capacitives (1..4)
static const Face FACES[NB_FACES] = {
  { -0.85655f, -0.39397f,  0.33333f, 11, 3 },  // face 0
  { -0.33514f, -0.88123f,  0.33333f, 13, 2 },  // face 1
  { -0.93074f, -0.15037f, -0.33333f,  5, 3 },  // face 2
  { -0.45519f, -0.48708f, -0.74536f,  2, 2 },  // face 3
  { -0.08709f, -0.93878f, -0.33333f,  6, 2 },  // face 4
  { -0.64942f,  0.15066f,  0.74536f, 17, 4 },  // face 5
  {  0.19423f, -0.63774f,  0.74536f, 18, 4 },  // face 6
  {  0.00000f,  0.00000f,  1.00000f, 20, 4 },  // face 7
  { -0.76946f,  0.54481f, -0.33333f,  7, 3 },  // face 8
  { -0.59560f,  0.73086f,  0.33333f, 12, 3 },  // face 9
  {  0.76946f, -0.54481f,  0.33333f, 14, 2 },  // face 10
  {  0.45519f,  0.48708f,  0.74536f, 19, 4 },  // face 11
  {  0.93074f,  0.15037f,  0.33333f, 16, 1 },  // face 12
  { -0.19423f,  0.63774f, -0.74536f,  3, 3 },  // face 13
  {  0.08709f,  0.93878f,  0.33333f, 15, 4 },  // face 14
  {  0.33514f,  0.88123f, -0.33333f,  8, 1 },  // face 15
  { -0.00000f, -0.00000f, -1.00000f,  1, 1 },  // face 16
  {  0.59560f, -0.73086f, -0.33333f,  9, 2 },  // face 17
  {  0.64942f, -0.15066f, -0.74536f,  4, 1 },  // face 18
  {  0.85655f,  0.39397f, -0.33333f, 10, 1 },  // face 19
};

// groupe (1..4) -> broche nRF52 qui pilote ses pastilles (via le fil et la pastille Gx du circuit)
static const uint8_t GROUPE_GPIO[5] = { 0, 13, 18, 12, 11 };
// groupe 1 -> G3, groupe 2 -> G4, groupe 3 -> G2, groupe 4 -> G1
#define FACE_RECHARGE 16
