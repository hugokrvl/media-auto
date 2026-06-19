"""
Vide la table `posts` (remet le planning à zéro).
DESTRUCTIF et IRRÉVERSIBLE — supprime TOUS les posts (pending/approved/posted).

Sécurité : ne s'exécute que si la variable d'environnement RESET_CONFIRM == "RESET".
Lancé via le workflow reset_planning.yml (déclenchement manuel + saisie "RESET").

Les images déjà uploadées dans le bucket post-images deviennent orphelines mais
restent inoffensives (espace seulement). On ne touche pas au bucket ici.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storage

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def main():
    if os.environ.get("RESET_CONFIRM", "") != "RESET":
        print("⛔ Annulé : RESET_CONFIRM != 'RESET'. Aucune suppression.")
        sys.exit(1)

    sb = storage.get_client()

    # Compte avant
    before = sb.table("posts").select("id", count="exact").execute()
    n = before.count if before.count is not None else len(before.data or [])
    print(f"Posts actuellement en base : {n}")

    if n == 0:
        print("✅ Base déjà vide — rien à faire.")
        return

    # Supprime TOUTES les lignes (filtre qui matche tout : id != uuid nul)
    sb.table("posts").delete().neq("id", _ZERO_UUID).execute()

    # Vérifie
    after = sb.table("posts").select("id", count="exact").execute()
    m = after.count if after.count is not None else len(after.data or [])
    if m == 0:
        print(f"✅ Base vidée : {n} post(s) supprimé(s). Planning propre.")
    else:
        print(f"⚠️ Il reste {m} post(s) après suppression — vérifier les droits RLS.")
        sys.exit(1)


if __name__ == "__main__":
    main()
