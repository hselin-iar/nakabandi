"""Internal package: not part of the shared facade. Reached only from nakabandi.main and from
each module's own infrastructure layer, which imports Base through the shared facade
(nakabandi.shared.Base), never this package path directly (DOC 2 §2.6 facade rule)."""
