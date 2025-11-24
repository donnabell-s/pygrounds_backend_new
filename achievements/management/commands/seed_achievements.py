from django.core.management.base import BaseCommand
from achievements.models import Achievement, UserAchievement
from typing import Optional, List, Tuple

# Default achievements you want in the system.
# (code, title, description, unlocked_zone)
DEFAULT_ACHIEVEMENTS: List[Tuple[str, str, str, Optional[int]]] = [
    (
        "game_enthusiast",
        "Game Enthusiast",
        "Complete 20 minigame sessions.",
        None,
    ),
    (
        "perfection_seeker",
        "Perfection Seeker",
        "Finish 5 perfect minigame sessions (no mistakes).",
        None,
    ),
    (
        "speed_solver",
        "Speed Solver (Concept)",
        "Complete a concept game (crossword/wordsearch) perfectly under 60 seconds.",
        None,
    ),
    (
        "first_steps",
        "First Concept Clear",
        "Complete your first concept game (crossword/wordsearch).",
        None,
    ),
    (
        "zone_unlocker",
        "Zone Unlocker",
        "Unlock a new learning zone.",
        None,  # Set a zone ID if zones are mapped numerically.
    ),
]

class Command(BaseCommand):
    help = "Seed (upsert) the default Achievement entries. Idempotent: will not duplicate existing codes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update title/description/unlocked_zone for existing achievements with same code.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete ALL achievements (and related user unlocks) before seeding.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        update_existing: bool = options.get("update", False)
        do_reset: bool = options.get("reset", False)
        dry_run: bool = options.get("dry_run", False)

        # Print active flags to make runs explicit in logs
        self.stdout.write(
            f"Flags -> update={update_existing}, reset={do_reset}, dry_run={dry_run}"
        )
        
        if do_reset:
            # Clear user unlocks first to avoid FK issues, then achievements
            if dry_run:
                ua_deleted = UserAchievement.objects.count()
                a_deleted = Achievement.objects.count()
                self.stdout.write(self.style.WARNING(
                    f"[DRY-RUN] Would delete {ua_deleted} user unlocks and {a_deleted} achievements."
                ))
            else:
                ua_deleted, _ = UserAchievement.objects.all().delete()
                a_deleted, _ = Achievement.objects.all().delete()
                self.stdout.write(self.style.WARNING(
                    f"Reset complete. Deleted {ua_deleted} user unlocks and {a_deleted} achievements."
                ))
        created_count = 0
        updated_count = 0

        for code, title, desc, zone in DEFAULT_ACHIEVEMENTS:
            # Try to get existing by code first to enable dry-run branching cleanly
            try:
                obj = Achievement.objects.get(code=code)
                created = False
            except Achievement.DoesNotExist:
                obj = None
                created = True

            if created:
                created_count += 1
                if dry_run:
                    self.stdout.write(self.style.SUCCESS(f"[DRY-RUN] Would create achievement: {code}"))
                else:
                    obj = Achievement.objects.create(
                        code=code,
                        title=title,
                        description=desc,
                        unlocked_zone=zone,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Created achievement: {code}"))
            else:
                if update_existing:
                    changed = False
                    changes = {}
                    if obj.title != title:
                        changes["title"] = (obj.title, title)
                        obj.title = title
                        changed = True
                    if obj.description != desc:
                        changes["description"] = (obj.description, desc)
                        obj.description = desc
                        changed = True
                    if obj.unlocked_zone != zone:
                        changes["unlocked_zone"] = (obj.unlocked_zone, zone)
                        obj.unlocked_zone = zone
                        changed = True
                    if changed:
                        if dry_run:
                            updated_count += 1
                            self.stdout.write(self.style.WARNING(
                                f"[DRY-RUN] Would update {code}: " + ", ".join(
                                    f"{k}: '{v[0]}' -> '{v[1]}'" for k, v in changes.items()
                                )
                            ))
                        else:
                            obj.save()
                            updated_count += 1
                            self.stdout.write(self.style.WARNING(f"Updated achievement: {code}"))
                    else:
                        self.stdout.write(f"No changes for achievement: {code}")
                else:
                    self.stdout.write(f"Skipped existing achievement (use --update to modify): {code}")

        summary = (
            f"Seed complete. Created: {created_count}. Updated: {updated_count}. "
            f"Total in DB: {Achievement.objects.count()}"
        )
        self.stdout.write(self.style.SUCCESS(summary))
