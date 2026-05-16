"""
One-shot vault setup command.
Creates the Vault Home Page under the Wagtail default home page.
Safe to run multiple times (skips if already exists).

Usage:
    make vault-setup
"""
from django.core.management.base import BaseCommand
from wagtail.models import Page


class Command(BaseCommand):
    help = "Create initial Vault Home Page in Wagtail (idempotent)"

    def handle(self, *args, **options):
        from media_vault.pages import VaultHomePage

        if VaultHomePage.objects.exists():
            self.stdout.write(self.style.WARNING("Vault Home Page already exists — skipping."))
            for p in VaultHomePage.objects.all():
                self.stdout.write(f"  Existing: {p.title} → {p.url}")
            return

        home = Page.objects.filter(depth=2).first()
        if not home:
            self.stdout.write(self.style.ERROR("No depth-2 page found. Run migrations first."))
            return

        vault = VaultHomePage(
            title="Media Vault",
            slug="vault",
            tagline="Your Google media, organized.",
            intro="Browse, review, and manage all your backed-up Google photos and videos.",
        )
        home.add_child(instance=vault)
        vault.save_revision().publish()
        self.stdout.write(self.style.SUCCESS(f"Created Vault Home Page: {vault.url}"))
        self.stdout.write("Next steps:")
        self.stdout.write("  1. Visit /cms/ and add child pages (Media Gallery, Photo Review, Video Review)")
        self.stdout.write("  2. Upload images at /cms/images/")
        self.stdout.write("  3. Upload videos at /cms/media/")
