# Intégrer les dés MCDice dans Mandragore : Mentor et Sage en direct

Relu contre le dépôt `Mandragore-ai/Mandragore` le 23 nov. 2026. Le Mentor et le journal en direct vivent sur la branche **`codex/taverne-sage-context`** ; le Tabletop Kit vit sur la branche `codex/android-tabletop-sandbox-20261015`. Rien n'existe encore sur `main` pour le direct. Ce document décrit ce qu'il faut ajouter, sans toucher au dépôt Mandragore.

## 1. Où les dés se branchent

```
dés MCDice ──Bluetooth──► tablette du MJ (pupitre)
                               │  même horloge que le micro
                               ▼
               journal en direct du Barde (BardLiveEvents, ajout seul)
                 répliques {action:'turn'}  +  jets {action:'roll'}   ← nouveau
                               │
               ┌───────────────┴────────────────┐
               ▼                                ▼
     Mentor (JDR en direct)              Sage en direct (jeux de plateau,
     souffleur → bande 10+ / 7–9 / 6−    Tabletop Kit : source « mcdice »)
```

## 2. Ce que fait le Mentor aujourd'hui, et ce que le dé change

| Aujourd'hui (branche taverne) | Avec MCDice |
|---|---|
| Le résultat d'un jet est **deviné dans la parole** : `lib/mentor/souffleur.ts`, fonction `roll()`, repère « j'ai fait 8 », « ça donne neuf »… | Le jet arrive **comme un fait** dans le journal, avec la place du joueur et la valeur exacte |
| La reconnaissance vocale rate des mots de dés : la recette `BARDE_JOURNAL_DIRECT.md` note « jeter les dés » transcrit « jeter l'idée » | Aucune dépendance à la voix pour le chiffre |
| `conduct()` relie une action annoncée (« je défie le danger ») au résultat qui suit, puis `dwIntervention(nom, résultat)` choisit la politique (choix à 7–9, riposte, 6−) | Même chaîne, mais le résultat vient du jet : **somme des dés + caractéristique de la fiche du PJ** (le Mentor a déjà les fiches : `lib/mentor/characters.ts`) |
| Les dés « autres » (d4…d20, dégâts) sont seulement repérés par la parole (`otherDice`) | Le type du dé est connu : un jet d8 de dégâts n'est jamais pris pour un jet d'action 2d6 |

## 3. Les ajouts nécessaires

### a. Journal en direct : une ligne « jet »
- Fichier fourni : `logiciel/mcdice-web/journal-roll.ts`.
  - **`JournalRollRow`** : `{action:'roll', roll:{atMs, owner, dice[], sum, source}}`. `atMs` utilise la même horloge que `turn.arrivedMs`. `owner` est la **fiche de personnage** associée au dé (`{kind:'character', id}`, l'identifiant des fiches du Mentor) ou **le MJ** (`{kind:'gm'}`).
  - **`regrouperJets()`** : les dés d'un même propriétaire arrêtés à moins de 1,5 s l'un de l'autre forment un seul jet. C'est le cas des 2d6 de PbtA.
  - **`isJournalRollRow()`** : la validation serveur, écrite dans le style de `lib/bard-live/validate.ts`.
- Dans Mandragore, il faut :
  1. ajouter cette variante au type `JournalRow` (`lib/bard-live/journal.mts`) ;
  2. l'accepter dans `isJournalRow` ;
  3. la faire passer dans `materialize()` : la garder à part de `segments`, pour ne pas polluer la transcription ;
  4. pousser la ligne par la route existante `POST /api/sessions/[id]/live`, action `events`. Aucune nouvelle table ni route n'est nécessaire.

### b. Mentor
- Lui donner le jet structuré en plus du texte. Par exemple, un paramètre `jet?: {label, sum, faces[]}` dans `conduct()` : s'il est présent, il remplace `roll(s)`.
- **Total PbtA = somme des 2d6 + caractéristique de l'action**, lue sur la fiche du personnage associé au dé. **Décidé** : la caractéristique découle de **l'action déclenchée**, que le Mentor doit reconnaître dans la fiction (« je saute par-dessus le gouffre » → Défier le Danger par la Dextérité). Le chantier principal est donc la **reconnaissance des actions déclenchées**, déjà amorcée dans `souffleur.ts` (`namedMove`, `triggers`). Tant qu'elle est incertaine, le pupitre affiche « 2d6 = 8, quelle caractéristique ? ».
- Le chiffre dit à voix haute reste un repli, pour les tables sans dés connectés.
- **Décidé** : chaque dé est associé à un joueur et à sa **fiche de personnage**, une fois pour toutes. L'association se fait dans l'Atelier ou au pupitre, en touchant la fiche puis en secouant le dé. Le pupitre affiche le dernier jet de chaque personnage.
- **Décidé** : le MJ a ses propres dés. Ils sont associés au MJ et le Mentor les lit, par exemple pour les dégâts d'un PNJ.

### c. Sage en direct (jeux de plateau)
- Fichier fourni : `logiciel/mcdice-web/tabletop-dice.ts`. C'est un module « mcdice » du Tabletop Kit qui en respecte les règles : désactivé par défaut, rien au chargement, événement versionné `dice.rolled`.
- Le Sage peut s'en servir pour résoudre une proposition en attente (« lancez pour la poussée »). La règle du kit s'applique toujours : une proposition, puis une confirmation explicite.

### d. Connexion aux dés
- Fichier fourni : `logiciel/mcdice-web/mcdice.ts`, en Web Bluetooth, pour Chrome et Edge sur ordinateur et sur Android.
- **Tablette iPad / iPhone** : passer par l'appli Capacitor déjà en place, avec l'extension `@capacitor-community/bluetooth-le`. Elle a la même API sur le web, sur Android et sur iOS. Il reste à ajouter à `mcdice.ts` un transport construit sur elle ; c'est la prochaine étape côté code.
- Un seul appareil, la tablette du pupitre, se connecte à tous les dés de la table : jusqu'à environ 7 dés.

## 4. Points à trancher
1. ~~Associer dé et joueur~~ : décidé, chaque dé est lié à un joueur et à sa fiche de personnage.
2. ~~Dés du MJ~~ : décidé, le MJ a ses dés et le Mentor les lit.
3. ~~Caractéristique~~ : décidé, le Mentor la déduit de l'action déclenchée qu'il a reconnue.
4. **Organized Play** : faut-il des jets signés pour l'anti-triche ? Le firmware du dé peut ajouter compteur et signature.
