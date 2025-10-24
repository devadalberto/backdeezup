# gmail_josevaldes_cleanup
Minimal backend-first pipeline to move media from Google Drive into Django-managed storage with a provable audit trail and safe deletion.
**Two proofs before delete:** (1) local file exists; (2) file imported as a MediaItem.
